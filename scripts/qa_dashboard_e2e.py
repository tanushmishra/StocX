import sys
import time
import traceback
from playwright.sync_api import sync_playwright

def run_qa():
    print("Starting detailed E2E Dashboard screenshot capture...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()

        try:
            print("1. Navigating to http://localhost:8501...")
            page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
            time.sleep(2)
            page.screenshot(path="docs/screenshots/01_initial_dashboard.png")
            print("Captured: 01_initial_dashboard.png")

            print("2. Entering thesis...")
            thesis_text = "Bullish on Indian IT, concerned about a US recession crash."
            thesis_input = page.locator("input[aria-label='Enter your market thesis']").first
            if not thesis_input.is_visible():
                thesis_input = page.locator("input[type='text']").first
            
            thesis_input.click()
            thesis_input.fill(thesis_text)
            page.keyboard.press("Enter")
            time.sleep(1)
            page.screenshot(path="docs/screenshots/02_thesis_input.png")
            print("Captured: 02_thesis_input.png")

            print("3. Clicking 'Build Hedge' button...")
            build_btn = page.locator("button:has-text('Build Hedge')").first
            build_btn.click()
            time.sleep(2)
            page.screenshot(path="docs/screenshots/03_pipeline_executing.png")
            print("Captured: 03_pipeline_executing.png")

            print("4. Waiting for pipeline execution to complete and results to render...")
            page.locator("text='Adversarial Risk Gate Verification'").wait_for(state="visible", timeout=90000)
            print("Adversarial Risk Gate Verification appeared!")
            time.sleep(3)

            # Helper to scroll and capture
            def capture_section(header_text, filename):
                loc = page.locator(f"text='{header_text}'").first
                if loc.is_visible():
                    loc.scroll_into_view_if_needed()
                    time.sleep(1.5)
                    page.screenshot(path=f"docs/screenshots/{filename}")
                    print(f"Captured: {filename}")
                else:
                    print(f"Header not found: {header_text}")

            capture_section("Adversarial Risk Gate Verification", "04_verification_summary.png")
            capture_section("Quantitative Risk & Performance Metrics", "05_metrics_cards.png")
            capture_section("Performance & Risk Analytics", "06_performance_analytics.png")
            capture_section("Statistical Cointegration & Correlation", "07_statistical_cointegration.png")
            capture_section("Pair Fundamental Comparison", "08_pair_fundamentals.png")
            capture_section("News Intelligence & Catalyst Audit", "09_news_intelligence.png")
            capture_section("Multi-Agent Execution Audit Trail", "10_agent_trace_audit.png")
            capture_section("Rejection & Risk Filter History", "10b_rejection_history_fixed.png")
            capture_section("Institutional CRO Report & Execution Plan", "11_cro_and_fno_plan.png")

            # Capture entire scrollable container height in high-res full page
            page.set_viewport_size({"width": 1600, "height": 3400})
            time.sleep(2)
            page.screenshot(path="docs/screenshots/12_full_page_overview.png")
            print("Captured: 12_full_page_overview.png")

            print("All screenshot captures completed successfully!")

        except Exception as exc:
            print("Error during QA run:", exc)
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == "__main__":
    run_qa()
