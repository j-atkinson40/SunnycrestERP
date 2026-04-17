"""Uline order automation script.

Logs in to uline.com, adds an item to the cart by item number,
and places the order using the tenant's pre-configured shipping
address and payment method.

Inputs
------
item_number : str   Uline product number, e.g. "S-15978"
quantity    : int   Number of units (boxes, cases, etc.)

Outputs
-------
confirmation_number : str | None
order_total         : float | None
estimated_delivery  : str | None
order_url           : str
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.playwright_scripts.base import PlaywrightScript, PlaywrightScriptError

logger = logging.getLogger(__name__)


class UlineOrderScript(PlaywrightScript):
    name = "uline_place_order"
    service_key = "uline"
    required_inputs = ["item_number", "quantity"]
    outputs = ["confirmation_number", "order_total", "estimated_delivery", "order_url"]

    async def execute(
        self,
        inputs: dict[str, Any],
        credentials: dict[str, str],
    ) -> dict[str, Any]:
        self.validate_inputs(inputs)

        # Import inside async to keep module importable without Playwright installed.
        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            raise PlaywrightScriptError(
                "Playwright is not installed. Run: pip install playwright && "
                "playwright install chromium",
                step="import",
            ) from e

        item_number = str(inputs["item_number"]).strip()
        quantity = int(inputs["quantity"])

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                # ── Step 1: Navigate and sign in ──────────────────────
                await page.goto("https://www.uline.com", wait_until="domcontentloaded")
                # Try to find sign-in link
                sign_in = page.locator('a[href*="sign-in"], a[href*="signin"], [data-test="sign-in"]').first
                await sign_in.click(timeout=8000)
                await page.wait_for_load_state("domcontentloaded")

                email_input = page.locator('#email, input[name="email"], input[type="email"]').first
                await email_input.fill(credentials.get("username", ""), timeout=8000)

                password_input = page.locator('#password, input[name="password"], input[type="password"]').first
                await password_input.fill(credentials.get("password", ""), timeout=5000)

                submit = page.locator('button[type="submit"], input[type="submit"]').first
                await submit.click(timeout=5000)
                await page.wait_for_load_state("networkidle", timeout=15000)

                if "sign-in" in page.url.lower() or "login" in page.url.lower():
                    screenshot = await self._take_screenshot(page, "uline_login_failed")
                    raise PlaywrightScriptError(
                        "Uline login failed — please verify credentials in Settings → External Accounts.",
                        screenshot_path=screenshot,
                        step="login",
                    )

                # ── Step 2: Go to product detail page ─────────────────
                await page.goto(
                    f"https://www.uline.com/Product_Detail?model={item_number}",
                    wait_until="domcontentloaded",
                )

                # ── Step 3: Set quantity and add to cart ───────────────
                qty_input = page.locator('input[name="qty"], input[id*="qty"], input[aria-label*="quantity"]').first
                await qty_input.fill(str(quantity), timeout=8000)

                add_to_cart = page.locator(
                    'button[data-test="add-to-cart"], button:has-text("Add to Cart"), '
                    'button:has-text("Add to cart")'
                ).first
                await add_to_cart.click(timeout=8000)
                await page.wait_for_load_state("networkidle", timeout=10000)

                # ── Step 4: Checkout ───────────────────────────────────
                await page.goto("https://www.uline.com/Cart", wait_until="domcontentloaded")

                checkout_btn = page.locator(
                    'button[data-test="checkout"], a[href*="checkout"], '
                    'button:has-text("Checkout"), a:has-text("Checkout")'
                ).first
                await checkout_btn.click(timeout=8000)
                await page.wait_for_load_state("networkidle", timeout=15000)

                # ── Step 5: Place order (use stored address + payment) ─
                place_order_btn = page.locator(
                    'button[data-test="place-order"], button:has-text("Place Order"), '
                    'button:has-text("Submit Order"), button:has-text("Place order")'
                ).first
                await place_order_btn.click(timeout=10000)
                await page.wait_for_load_state("networkidle", timeout=20000)

                # ── Step 6: Extract confirmation ───────────────────────
                confirmation: str | None = None
                order_total: float | None = None
                estimated_delivery: str | None = None

                # Confirmation number
                try:
                    confirm_el = page.locator(
                        '[data-test="confirmation-number"], '
                        '.confirmation-number, [class*="confirmation"] strong, '
                        'h1:has-text("Order Confirmed"), '
                        'p:has-text("Order #"), p:has-text("Confirmation")'
                    ).first
                    raw_confirm = await confirm_el.text_content(timeout=5000)
                    if raw_confirm:
                        # Extract just the number portion if embedded in a sentence
                        import re
                        m = re.search(r"[A-Z0-9]{6,}", raw_confirm.strip())
                        confirmation = m.group(0) if m else raw_confirm.strip()
                except Exception:
                    logger.warning("Could not extract Uline confirmation number")

                # Order total
                try:
                    total_el = page.locator(
                        '[data-test="order-total"], .order-total, '
                        '[class*="total"]:has-text("$"), '
                        'td:has-text("Order Total") + td, '
                        'span:has-text("Total:")'
                    ).first
                    total_text = await total_el.text_content(timeout=5000)
                    if total_text:
                        import re
                        m = re.search(r"\$?([\d,]+\.\d{2})", total_text)
                        if m:
                            order_total = float(m.group(1).replace(",", ""))
                except Exception:
                    logger.warning("Could not extract Uline order total")

                # Estimated delivery
                try:
                    delivery_el = page.locator(
                        '[data-test="estimated-delivery"], '
                        '[class*="delivery"]:has-text("Delivery"), '
                        'p:has-text("Estimated delivery")'
                    ).first
                    estimated_delivery = await delivery_el.text_content(timeout=3000)
                    if estimated_delivery:
                        estimated_delivery = estimated_delivery.strip()
                except Exception:
                    pass

                return {
                    "confirmation_number": confirmation,
                    "order_total": order_total,
                    "estimated_delivery": estimated_delivery,
                    "order_url": page.url,
                }

            except PlaywrightScriptError:
                raise
            except Exception as e:
                screenshot = await self._take_screenshot(page, "uline_error")
                raise PlaywrightScriptError(
                    f"Uline order failed at an unexpected step: {e}",
                    screenshot_path=screenshot,
                    step="unknown",
                ) from e
            finally:
                await browser.close()
