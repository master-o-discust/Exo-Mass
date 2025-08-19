"""
Exact Login Handler for Epic Games
Based on comprehensive analysis, this implements the precise interaction sequence:
1. Fill email using JavaScript
2. Click Continue button
3. Fill password field
4. Click Sign in button
"""
import asyncio
import logging
import random
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class ExactLoginHandler:
    """Handles Epic Games login with exact interaction sequence"""
    
    @staticmethod
    async def perform_exact_login(page, email: str, password: str) -> bool:
        """
        Perform exact login sequence based on comprehensive analysis
        
        Args:
            page: Playwright page object
            email: Email address
            password: Password
            
        Returns:
            bool: True if login sequence completed successfully
        """
        try:
            logger.info(f"🎯 {email} - Starting exact login sequence...")
            
            # STEP 1: Fill email using JavaScript (most reliable method)
            logger.info(f"📧 {email} - Step 1: Filling email via JavaScript...")
            
            email_result = await page.evaluate(f"""
                (email) => {{
                    // Find the email input field
                    const emailInput = document.querySelector('input[id="email"], input[name="email"], input[type="email"]');
                    if (emailInput) {{
                        // Set value directly
                        emailInput.value = email;
                        
                        // Dispatch events to ensure proper form handling
                        emailInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        emailInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        emailInput.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                        
                        return {{ success: true, value: emailInput.value }};
                    }}
                    return {{ success: false, error: 'Email input not found' }};
                }}
            """, email)
            
            if not email_result.get('success') or email_result.get('value') != email:
                logger.error(f"❌ {email} - Step 1 failed: {email_result.get('error', 'Unknown error')}")
                return False
            
            logger.info(f"✅ {email} - Step 1 completed: Email filled successfully")
            await asyncio.sleep(2)  # Wait for form to process
            
            # STEP 2: Click Continue button
            logger.info(f"➡️ {email} - Step 2: Clicking Continue button...")
            
            continue_success = False
            try:
                # Try the exact selector from analysis
                continue_btn = await page.query_selector('button:has-text("Continue")')
                if continue_btn:
                    is_visible = await continue_btn.is_visible()
                    is_enabled = await continue_btn.is_enabled()
                    
                    if is_visible and is_enabled:
                        await continue_btn.click()
                        continue_success = True
                        logger.info(f"✅ {email} - Step 2 completed: Continue button clicked")
                    else:
                        logger.warning(f"⚠️ {email} - Continue button not interactive")
                else:
                    logger.warning(f"⚠️ {email} - Continue button not found")
            except Exception as e:
                logger.warning(f"⚠️ {email} - Continue button click failed: {e}")
            
            # Fallback: Use Enter key
            if not continue_success:
                logger.info(f"🔄 {email} - Using Enter key as Continue fallback...")
                await page.keyboard.press('Enter')
                logger.info(f"✅ {email} - Step 2 completed: Enter key pressed")
            
            await asyncio.sleep(3)  # Wait for password step to load
            
            # STEP 3: Fill password field
            logger.info(f"🔒 {email} - Step 3: Filling password field...")
            
            try:
                # Wait for password field to appear
                await page.wait_for_selector('input[type="password"]', timeout=10000)
                password_input = await page.query_selector('input[type="password"]')
                
                if password_input:
                    is_visible = await password_input.is_visible()
                    is_enabled = await password_input.is_enabled()
                    
                    if is_visible and is_enabled:
                        await password_input.fill(password)
                        logger.info(f"✅ {email} - Step 3 completed: Password filled successfully")
                    else:
                        logger.error(f"❌ {email} - Step 3 failed: Password field not interactive")
                        return False
                else:
                    logger.error(f"❌ {email} - Step 3 failed: Password field not found")
                    return False
            except Exception as e:
                logger.error(f"❌ {email} - Step 3 failed: {e}")
                return False
            
            await asyncio.sleep(2)  # Wait for form to process password
            
            # STEP 4: Click Sign in button (final submit)
            logger.info(f"🚀 {email} - Step 4: Clicking Sign in button...")
            
            signin_success = False
            try:
                # Try the exact selector from analysis
                signin_btn = await page.query_selector('button:has-text("Sign in")')
                if signin_btn:
                    is_visible = await signin_btn.is_visible()
                    is_enabled = await signin_btn.is_enabled()
                    
                    if is_visible and is_enabled:
                        await signin_btn.click()
                        signin_success = True
                        logger.info(f"✅ {email} - Step 4 completed: Sign in button clicked")
                    else:
                        logger.warning(f"⚠️ {email} - Sign in button not interactive")
                else:
                    logger.warning(f"⚠️ {email} - Sign in button not found")
            except Exception as e:
                logger.warning(f"⚠️ {email} - Sign in button click failed: {e}")
            
            # Fallback: Use Enter key
            if not signin_success:
                logger.info(f"🔄 {email} - Using Enter key as Sign in fallback...")
                await page.keyboard.press('Enter')
                logger.info(f"✅ {email} - Step 4 completed: Enter key pressed")
            
            logger.info(f"🎉 {email} - Exact login sequence completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ {email} - Exact login sequence failed: {e}")
            return False
    
    @staticmethod
    async def verify_login_form_state(page) -> dict:
        """
        Verify the current state of the login form
        
        Returns:
            dict: Form state information
        """
        try:
            form_state = await page.evaluate("""
                () => {
                    const emailInput = document.querySelector('input[id="email"], input[name="email"], input[type="email"]');
                    const passwordInput = document.querySelector('input[type="password"]');
                    const continueBtn = document.querySelector('button:has-text("Continue")');
                    const signinBtn = document.querySelector('button:has-text("Sign in")');
                    
                    return {
                        email_field: {
                            found: !!emailInput,
                            visible: emailInput ? emailInput.offsetParent !== null : false,
                            enabled: emailInput ? !emailInput.disabled : false,
                            value: emailInput ? emailInput.value : ''
                        },
                        password_field: {
                            found: !!passwordInput,
                            visible: passwordInput ? passwordInput.offsetParent !== null : false,
                            enabled: passwordInput ? !passwordInput.disabled : false
                        },
                        continue_button: {
                            found: !!continueBtn,
                            visible: continueBtn ? continueBtn.offsetParent !== null : false,
                            enabled: continueBtn ? !continueBtn.disabled : false
                        },
                        signin_button: {
                            found: !!signinBtn,
                            visible: signinBtn ? signinBtn.offsetParent !== null : false,
                            enabled: signinBtn ? !signinBtn.disabled : false
                        }
                    };
                }
            """)
            
            return form_state
            
        except Exception as e:
            logger.error(f"❌ Failed to verify form state: {e}")
            return {}
    
    @staticmethod
    async def debug_form_elements(page) -> None:
        """Debug helper to log current form elements"""
        try:
            elements_info = await page.evaluate("""
                () => {
                    const inputs = Array.from(document.querySelectorAll('input'));
                    const buttons = Array.from(document.querySelectorAll('button'));
                    
                    return {
                        inputs: inputs.map(input => ({
                            type: input.type,
                            id: input.id,
                            name: input.name,
                            placeholder: input.placeholder,
                            visible: input.offsetParent !== null,
                            enabled: !input.disabled
                        })),
                        buttons: buttons.map(button => ({
                            text: button.textContent.trim().substring(0, 50),
                            visible: button.offsetParent !== null,
                            enabled: !button.disabled
                        }))
                    };
                }
            """)
            
            logger.info("🔍 Current form elements:")
            logger.info(f"   Inputs: {len(elements_info.get('inputs', []))}")
            for i, inp in enumerate(elements_info.get('inputs', [])):
                logger.info(f"     {i+1}. type={inp['type']}, id={inp['id']}, name={inp['name']}, visible={inp['visible']}")
            
            logger.info(f"   Buttons: {len(elements_info.get('buttons', []))}")
            for i, btn in enumerate(elements_info.get('buttons', [])):
                logger.info(f"     {i+1}. text='{btn['text']}', visible={btn['visible']}")
                
        except Exception as e:
            logger.error(f"❌ Failed to debug form elements: {e}")