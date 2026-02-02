import sys
import os
import traceback

# Ensure app module is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

def run():
    try:
        from tests.test_rag_optimization import TestRagAntiGravity
        import unittest
        
        # Load tests
        suite = unittest.TestLoader().loadTestsFromTestCase(TestRagAntiGravity)
        
        # Run tests and write to file
        with open('test_summary.txt', 'w') as f:
            f.write("Running tests...\n")
            runner = unittest.TextTestRunner(stream=f, verbosity=2)
            result = runner.run(suite)
            
            f.write("\n\nSummary:\n")
            f.write(f"Ran: {result.testsRun}\n")
            f.write(f"Errors: {len(result.errors)}\n")
            f.write(f"Failures: {len(result.failures)}\n")
            
            if result.failures:
                f.write("\nFAILURES:\n")
                for test, trace in result.failures:
                    f.write(f"Test: {test}\n")
                    f.write(f"{trace}\n")
            
            if result.errors:
                f.write("\nERRORS:\n")
                for test, trace in result.errors:
                    f.write(f"Test: {test}\n")
                    f.write(f"{trace}\n")

    except Exception:
        with open('crash.log', 'w') as f:
            f.write(traceback.format_exc())
        print("CRASHED during imports/setup. Check crash.log")

if __name__ == '__main__':
    run()
