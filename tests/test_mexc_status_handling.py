#!/usr/bin/env python3
"""
Automated tests for MEXC cleanup and restart cycle status handling.

Tests all three status paths:
1. SUCCESS - Trade executed successfully
2. REJECTED - Quality filter rejection (normal operation)
3. FAILED - Actual error/failure

Usage:
    python tests/test_mexc_status_handling.py
"""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.cleanup_and_restart_mexc_cycle import MexcCycleManager


class TestMexcStatusHandling(unittest.TestCase):
    """Test all three status handling paths in cleanup_and_restart_mexc_cycle.py"""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = MexcCycleManager()
        
    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self.manager, 'notifier'):
            self.manager.notifier = None
    
    def _create_mock_result(self, status, **kwargs):
        """Create a mock trading cycle result with given status."""
        base_result = {
            'status': status,
            'cycle_time_ms': 5000.0,
            'ai_result': {
                'regime': 'trending',
                'trade_proposal': {
                    'strategy_name': 'momentum',
                    'confidence': 0.85,
                    'side': 'LONG',
                    'entry_price': 4700.0,
                    'stop_loss': 4650.0,
                    'take_profit': 4800.0,
                    'leverage': 10
                }
            },
            'execution': {
                'status': 'executed',
                'trade_id': 123,
                'order_id': 'order_456'
            }
        }
        
        if status == 'rejected':
            base_result.update({
                'rejection_reason': kwargs.get('rejection_reason', 'Quality score below threshold'),
                'quality_score': kwargs.get('quality_score', 75)
            })
        elif status == 'failed':
            base_result.update({
                'error': kwargs.get('error', 'Network timeout')
            })
        
        return base_result
    
    def test_step4_handles_success_status(self):
        """Test that step4 correctly handles success status."""
        mock_result = self._create_mock_result('success')
        
        # Create mock trading service
        mock_trading_service = AsyncMock()
        mock_trading_service.execute_trading_cycle = AsyncMock(return_value=mock_result)
        mock_trading_service.close = AsyncMock()
        
        # Run the test
        async def run_test():
            with patch('scripts.cleanup_and_restart_mexc_cycle.LiveTradingService', return_value=mock_trading_service):
                with patch('scripts.cleanup_and_restart_mexc_cycle.async_session_maker') as mock_session:
                    mock_session.return_value.__aenter__ = AsyncMock()
                    mock_session.return_value.__aexit__ = AsyncMock()
                    
                    result = await self.manager.step4_initiate_new_cycle()
                    
                    # Verify result structure
                    self.assertEqual(result['status'], 'success')
                    self.assertIn('cycle_time_ms', result)
                    self.assertIn('regime', result)
                    self.assertIn('strategy', result)
                    self.assertIn('execution_status', result)
                    self.assertEqual(result['execution_status'], 'executed')
                    self.assertEqual(result['trade_id'], 123)
                    
                    # Verify service was called
                    mock_trading_service.execute_trading_cycle.assert_called_once()
        
        asyncio.run(run_test())
        print("✅ Test passed: step4 handles SUCCESS status correctly")
    
    def test_step4_handles_rejected_status(self):
        """Test that step4 correctly handles rejected status (quality filter)."""
        mock_result = self._create_mock_result(
            'rejected',
            rejection_reason='Quality score below threshold',
            quality_score=75
        )
        
        # Create mock trading service
        mock_trading_service = AsyncMock()
        mock_trading_service.execute_trading_cycle = AsyncMock(return_value=mock_result)
        mock_trading_service.close = AsyncMock()
        
        # Run the test
        async def run_test():
            with patch('scripts.cleanup_and_restart_mexc_cycle.LiveTradingService', return_value=mock_trading_service):
                with patch('scripts.cleanup_and_restart_mexc_cycle.async_session_maker') as mock_session:
                    mock_session.return_value.__aenter__ = AsyncMock()
                    mock_session.return_value.__aexit__ = AsyncMock()
                    
                    result = await self.manager.step4_initiate_new_cycle()
                    
                    # Verify result structure for rejection
                    self.assertEqual(result['status'], 'rejected')
                    self.assertIn('rejection_reason', result)
                    self.assertIn('quality_score', result)
                    self.assertEqual(result['rejection_reason'], 'Quality score below threshold')
                    self.assertEqual(result['quality_score'], 75)
                    self.assertIn('cycle_time_ms', result)
                    
                    # Verify it's NOT marked as failed
                    self.assertNotEqual(result['status'], 'failed')
                    self.assertNotIn('error', result)
                    
                    # Verify service was called
                    mock_trading_service.execute_trading_cycle.assert_called_once()
        
        asyncio.run(run_test())
        print("✅ Test passed: step4 handles REJECTED status correctly (not misclassified as failed)")
    
    def test_step4_handles_failed_status(self):
        """Test that step4 correctly handles actual failure status."""
        mock_result = self._create_mock_result(
            'failed',
            error='Network timeout'
        )
        
        # Create mock trading service
        mock_trading_service = AsyncMock()
        mock_trading_service.execute_trading_cycle = AsyncMock(return_value=mock_result)
        mock_trading_service.close = AsyncMock()
        
        # Run the test
        async def run_test():
            with patch('scripts.cleanup_and_restart_mexc_cycle.LiveTradingService', return_value=mock_trading_service):
                with patch('scripts.cleanup_and_restart_mexc_cycle.async_session_maker') as mock_session:
                    mock_session.return_value.__aenter__ = AsyncMock()
                    mock_session.return_value.__aexit__ = AsyncMock()
                    
                    result = await self.manager.step4_initiate_new_cycle()
                    
                    # Verify result structure for failure
                    self.assertEqual(result['status'], 'failed')
                    self.assertIn('error', result)
                    self.assertEqual(result['error'], 'Network timeout')
                    
                    # Verify it's NOT marked as success or rejected
                    self.assertNotEqual(result['status'], 'success')
                    self.assertNotEqual(result['status'], 'rejected')
                    
                    # Verify service was called
                    mock_trading_service.execute_trading_cycle.assert_called_once()
        
        asyncio.run(run_test())
        print("✅ Test passed: step4 handles FAILED status correctly")
    
    def test_step5_reports_rejection_correctly(self):
        """Test that step5 sends proper rejection report (not failure notification)."""
        rejected_trade_info = {
            'status': 'rejected',
            'cycle_time_ms': 5000.0,
            'rejection_reason': 'Quality score below threshold',
            'quality_score': 75
        }
        
        # Mock Telegram notifier
        mock_notifier = AsyncMock()
        mock_notifier.send_message = AsyncMock(return_value=True)
        self.manager.notifier = mock_notifier
        
        # Run the test
        async def run_test():
            await self.manager.step5_send_new_trade_report(rejected_trade_info)
            
            # Verify notification was sent
            mock_notifier.send_message.assert_called_once()
            
            # Verify the message content (should be rejection report, not failure)
            call_args = mock_notifier.send_message.call_args[0][0]
            
            # Should contain rejection-related keywords
            self.assertIn('REJECTED', call_args)
            self.assertIn('Quality Filter', call_args)
            self.assertIn('Quality Score', call_args)
            self.assertIn('75/100', call_args)
            
            # Should NOT contain failure-related keywords
            self.assertNotIn('Validation Cycle Failed', call_args)
            self.assertNotIn('Error:', call_args)
            
            # Should contain severity information
            self.assertIn('LOW QUALITY', call_args)
        
        asyncio.run(run_test())
        print("✅ Test passed: step5 sends REJECTION report correctly (not failure notification)")
    
    def test_step5_reports_failure_correctly(self):
        """Test that step5 sends proper failure notification for actual errors."""
        failed_trade_info = {
            'status': 'failed',
            'error': 'Network timeout'
        }
        
        # Mock Telegram notifier
        mock_notifier = AsyncMock()
        mock_notifier.send_message = AsyncMock(return_value=True)
        self.manager.notifier = mock_notifier
        
        # Run the test
        async def run_test():
            await self.manager.step5_send_new_trade_report(failed_trade_info)
            
            # Verify notification was sent
            mock_notifier.send_message.assert_called_once()
            
            # Verify the message content (should be failure notification)
            call_args = mock_notifier.send_message.call_args[0][0]
            
            # Should contain failure-related keywords
            self.assertIn('Validation Cycle Failed', call_args)
            self.assertIn('Error:', call_args)
            self.assertIn('Network timeout', call_args)
            
            # Should NOT contain rejection-related keywords
            self.assertNotIn('Quality Filter', call_args)
            self.assertNotIn('Quality Score', call_args)
        
        asyncio.run(run_test())
        print("✅ Test passed: step5 sends FAILURE notification correctly")
    
    def test_step5_reports_success_correctly(self):
        """Test that step5 sends proper execution report for successful trades."""
        success_trade_info = {
            'status': 'success',
            'cycle_time_ms': 5000.0,
            'regime': 'trending',
            'strategy': 'momentum',
            'confidence': 0.85,
            'side': 'LONG',
            'entry_price': 4700.0,
            'stop_loss': 4650.0,
            'take_profit': 4800.0,
            'leverage': 10,
            'execution_status': 'executed',
            'trade_id': 123,
            'order_id': 'order_456'
        }
        
        # Mock Telegram notifier
        mock_notifier = AsyncMock()
        mock_notifier.send_message = AsyncMock(return_value=True)
        self.manager.notifier = mock_notifier
        
        # Run the test
        async def run_test():
            await self.manager.step5_send_new_trade_report(success_trade_info)
            
            # Verify notification was sent
            mock_notifier.send_message.assert_called_once()
            
            # Verify the message content (should be execution report)
            call_args = mock_notifier.send_message.call_args[0][0]
            
            # Should contain success-related keywords
            self.assertIn('New Trade Executed', call_args)
            self.assertIn('EXECUTED', call_args)
            self.assertIn('Trade ID', call_args)
            self.assertIn('#123', call_args)
            
            # Should NOT contain rejection or failure keywords
            self.assertNotIn('REJECTED', call_args)
            self.assertNotIn('Failed', call_args)
        
        asyncio.run(run_test())
        print("✅ Test passed: step5 sends SUCCESS report correctly")
    
    def test_rejection_with_high_score(self):
        """Test rejection reporting with high quality score (80+)."""
        rejected_trade_info = {
            'status': 'rejected',
            'cycle_time_ms': 5000.0,
            'rejection_reason': 'Marginal conditions',
            'quality_score': 85
        }
        
        # Mock Telegram notifier
        mock_notifier = AsyncMock()
        mock_notifier.send_message = AsyncMock(return_value=True)
        self.manager.notifier = mock_notifier
        
        # Run the test
        async def run_test():
            await self.manager.step5_send_new_trade_report(rejected_trade_info)
            
            # Verify the message content
            call_args = mock_notifier.send_message.call_args[0][0]
            
            # Should show MARGINAL severity for score >= 80
            self.assertIn('MARGINAL', call_args)
            self.assertIn('85/100', call_args)
        
        asyncio.run(run_test())
        print("✅ Test passed: rejection with HIGH score shows MARGINAL severity")
    
    def test_rejection_with_low_score(self):
        """Test rejection reporting with low quality score (<60)."""
        rejected_trade_info = {
            'status': 'rejected',
            'cycle_time_ms': 5000.0,
            'rejection_reason': 'Poor market conditions',
            'quality_score': 45
        }
        
        # Mock Telegram notifier
        mock_notifier = AsyncMock()
        mock_notifier.send_message = AsyncMock(return_value=True)
        self.manager.notifier = mock_notifier
        
        # Run the test
        async def run_test():
            await self.manager.step5_send_new_trade_report(rejected_trade_info)
            
            # Verify the message content
            call_args = mock_notifier.send_message.call_args[0][0]
            
            # Should show POOR QUALITY severity for score < 60
            self.assertIn('POOR QUALITY', call_args)
            self.assertIn('45/100', call_args)
        
        asyncio.run(run_test())
        print("✅ Test passed: rejection with LOW score shows POOR QUALITY severity")
    
    def test_all_three_statuses_are_mutually_exclusive(self):
        """Test that all three statuses are handled independently."""
        statuses_tested = []
        
        for status, expected_key in [('success', 'trade_id'), ('rejected', 'quality_score'), ('failed', 'error')]:
            mock_result = self._create_mock_result(status)
            
            # Create mock trading service
            mock_trading_service = AsyncMock()
            mock_trading_service.execute_trading_cycle = AsyncMock(return_value=mock_result)
            mock_trading_service.close = AsyncMock()
            
            async def run_test():
                with patch('scripts.cleanup_and_restart_mexc_cycle.LiveTradingService', return_value=mock_trading_service):
                    with patch('scripts.cleanup_and_restart_mexc_cycle.async_session_maker') as mock_session:
                        mock_session.return_value.__aenter__ = AsyncMock()
                        mock_session.return_value.__aexit__ = AsyncMock()
                        
                        result = await self.manager.step4_initiate_new_cycle()
                        statuses_tested.append(result['status'])
                        self.assertIn(expected_key, result)
            
            asyncio.run(run_test())
        
        # Verify all three statuses were tested
        self.assertEqual(len(statuses_tested), 3)
        self.assertIn('success', statuses_tested)
        self.assertIn('rejected', statuses_tested)
        self.assertIn('failed', statuses_tested)
        
        print("✅ Test passed: all three statuses are handled independently and correctly")


class TestStatusHandlingEdgeCases(unittest.TestCase):
    """Test edge cases in status handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = MexcCycleManager()
    
    def test_rejection_with_missing_reason(self):
        """Test rejection handling when reason is missing."""
        rejected_trade_info = {
            'status': 'rejected',
            'cycle_time_ms': 5000.0,
            'quality_score': 75
            # rejection_reason is missing
        }
        
        # Mock Telegram notifier
        mock_notifier = AsyncMock()
        mock_notifier.send_message = AsyncMock(return_value=True)
        self.manager.notifier = mock_notifier
        
        # Run the test
        async def run_test():
            await self.manager.step5_send_new_trade_report(rejected_trade_info)
            
            # Should use default 'Unknown' reason
            call_args = mock_notifier.send_message.call_args[0][0]
            self.assertIn('Unknown', call_args)
        
        asyncio.run(run_test())
        print("✅ Test passed: handles missing rejection reason gracefully")
    
    def test_failure_with_missing_error(self):
        """Test failure handling when error message is missing."""
        failed_trade_info = {
            'status': 'failed'
            # error is missing
        }
        
        # Mock Telegram notifier
        mock_notifier = AsyncMock()
        mock_notifier.send_message = AsyncMock(return_value=True)
        self.manager.notifier = mock_notifier
        
        # Run the test
        async def run_test():
            await self.manager.step5_send_new_trade_report(failed_trade_info)
            
            # Should use default 'Unknown error'
            call_args = mock_notifier.send_message.call_args[0][0]
            self.assertIn('Unknown error', call_args)
        
        asyncio.run(run_test())
        print("✅ Test passed: handles missing error message gracefully")


def run_tests():
    """Run all tests and display results."""
    print("\n" + "="*80)
    print("MEXC STATUS HANDLING AUTOMATED TESTS")
    print("="*80)
    print(f"Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMexcStatusHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestStatusHandlingEdgeCases))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total tests: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Completed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Exit code
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED - Status handling is working correctly!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Please review the failures above")
        return 1


if __name__ == '__main__':
    exit_code = run_tests()
    sys.exit(exit_code)
