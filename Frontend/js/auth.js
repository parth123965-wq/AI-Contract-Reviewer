/* ==========================================
   AI Contract Reviewer - Authentication Handler
========================================== */

document.addEventListener("DOMContentLoaded", () => {
  if (typeof isAuthenticated === "function" && isAuthenticated()) {
    const path = window.location.pathname;
    if (path.endsWith("index.html") || path.endsWith("register.html") || path.endsWith("/")) {
      window.location.replace("dashboard.html");
      return;
    }
  }

  initPasswordToggles();

  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", handleLoginSubmit);
  }

  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    registerForm.addEventListener("submit", handleRegisterSubmit);
  }
});

/* Toast Notification Utility */
function showToast(message, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === 'error' ? '⚠️' : '✓'}</span> <div>${message}</div>`;

  container.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.add("show");
  });

  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* Password Toggle Handler */
function initPasswordToggles() {
  const togglePassBtn = document.getElementById("togglePassword");
  if (togglePassBtn) {
    togglePassBtn.addEventListener("click", () => {
      const input = document.getElementById("password");
      if (input) {
        const type = input.getAttribute("type") === "password" ? "text" : "password";
        input.setAttribute("type", type);
        togglePassBtn.textContent = type === "password" ? "👁️" : "🙈";
      }
    });
  }

  const toggleRegPassBtn = document.getElementById("toggleRegPassword");
  if (toggleRegPassBtn) {
    toggleRegPassBtn.addEventListener("click", () => {
      const input = document.getElementById("register-password");
      if (input) {
        const type = input.getAttribute("type") === "password" ? "text" : "password";
        input.setAttribute("type", type);
        toggleRegPassBtn.textContent = type === "password" ? "👁️" : "🙈";
      }
    });
  }
}

let currentLoginMode = "user"; // "user" or "admin"

/* Mode Toggle Handlers */
document.addEventListener("DOMContentLoaded", () => {
  const userBtn = document.getElementById("userModeBtn");
  const adminBtn = document.getElementById("adminModeBtn");
  const titleEl = document.getElementById("login-title");
  const subtitleEl = document.getElementById("login-subtitle");
  const footerEl = document.getElementById("auth-footer");
  const submitBtn = document.getElementById("loginButton");

  if (userBtn && adminBtn) {
    userBtn.addEventListener("click", () => {
      currentLoginMode = "user";
      userBtn.className = "btn btn-sm btn-primary";
      adminBtn.className = "btn btn-sm btn-ghost";
      if (titleEl) titleEl.textContent = "Welcome Back";
      if (subtitleEl) subtitleEl.textContent = "Login to access your contract intelligence workspace";
      if (footerEl) footerEl.style.display = "block";
      if (submitBtn) submitBtn.textContent = "Sign In";
    });

    adminBtn.addEventListener("click", () => {
      currentLoginMode = "admin";
      adminBtn.className = "btn btn-sm btn-primary";
      userBtn.className = "btn btn-sm btn-ghost";
      if (titleEl) titleEl.textContent = "Admin Control Panel Login";
      if (subtitleEl) subtitleEl.textContent = "Authenticate with administrator credentials to access platform controls";
      if (footerEl) footerEl.style.display = "none";
      if (submitBtn) submitBtn.textContent = "Sign In as Admin";
    });
  }
});

/* Input Validations */
function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/* Login Submit Handler */
async function handleLoginSubmit(event) {
  event.preventDefault();

  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const submitBtn = document.getElementById("loginButton");

  const email = emailInput ? emailInput.value.trim() : "";
  const password = passwordInput ? passwordInput.value : "";

  if (!email || !password) {
    showToast("Please enter both email and password.", "error");
    return;
  }

  if (!validateEmail(email)) {
    showToast("Please enter a valid email address.", "error");
    return;
  }

  try {
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = currentLoginMode === "admin" ? "Authenticating Admin..." : "Signing In...";
    }

    if (currentLoginMode === "admin") {
      await adminLogin(email, password);
      showToast("Admin login successful! Redirecting to Admin Panel...", "success");
      setTimeout(() => {
        window.location.href = "admin.html";
      }, 600);
    } else {
      await login(email, password);
      showToast("Login successful! Redirecting...", "success");
      const savedUser = JSON.parse(localStorage.getItem(API_CONFIG.USER_KEY) || "{}");
      setTimeout(() => {
        if (savedUser && savedUser.is_admin) {
          window.location.href = "admin.html";
        } else {
          window.location.href = "dashboard.html";
        }
      }, 600);
    }
  } catch (error) {
    showToast(error.message || "Failed to sign in. Please try again.", "error");
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = currentLoginMode === "admin" ? "Sign In as Admin" : "Sign In";
    }
  }
}

let pendingRegisterEmail = "";
let pendingRegisterPassword = "";

/* Register Submit Handler */
async function handleRegisterSubmit(event) {
  event.preventDefault();

  const usernameInput = document.getElementById("username");
  const emailInput = document.getElementById("register-email");
  const passwordInput = document.getElementById("register-password");
  const confirmPasswordInput = document.getElementById("confirm-password");
  const submitBtn = document.getElementById("registerButton");

  const username = usernameInput ? usernameInput.value.trim() : "";
  const email = emailInput ? emailInput.value.trim() : "";
  const password = passwordInput ? passwordInput.value : "";
  const confirmPassword = confirmPasswordInput ? confirmPasswordInput.value : "";

  if (!username || !email || !password || !confirmPassword) {
    showToast("Please fill in all required fields.", "error");
    return;
  }

  if (!validateEmail(email)) {
    showToast("Please enter a valid email address.", "error");
    return;
  }

  if (password.length < 8) {
    showToast("Password must be at least 8 characters long.", "error");
    return;
  }

  if (password !== confirmPassword) {
    showToast("Passwords do not match.", "error");
    return;
  }

  try {
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Creating Account...";
    }

    const res = await register(email, password, username);
    pendingRegisterEmail = email;
    pendingRegisterPassword = password;

    showToast(res.message || "Registration successful! OTP code sent to your email.", "success");
    openOtpModal(email);

  } catch (error) {
    showToast(error.message || "Registration failed. Please try again.", "error");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Create Account & Get Started";
    }
  }
}

/* OTP Modal Event Listeners */
function openOtpModal(email) {
  const modal = document.getElementById("otpModal");
  const targetEmailEl = document.getElementById("otpEmailTarget");
  if (targetEmailEl) targetEmailEl.textContent = email;
  if (modal) modal.classList.add("active");
}

function closeOtpModal() {
  const modal = document.getElementById("otpModal");
  if (modal) modal.classList.remove("active");
}

document.addEventListener("DOMContentLoaded", () => {
  const closeBtn = document.getElementById("closeOtpModalBtn");
  if (closeBtn) closeBtn.addEventListener("click", closeOtpModal);

  const otpForm = document.getElementById("otpForm");
  if (otpForm) otpForm.addEventListener("submit", handleOtpSubmit);

  const resendBtn = document.getElementById("resendOtpBtn");
  if (resendBtn) resendBtn.addEventListener("click", handleResendOtp);
});

async function handleOtpSubmit(e) {
  e.preventDefault();
  const otpInput = document.getElementById("otpCodeInput");
  const submitBtn = document.getElementById("submitOtpBtn");
  const otpCode = otpInput ? otpInput.value.trim() : "";

  if (!otpCode || otpCode.length < 4) {
    showToast("Please enter a valid OTP code.", "error");
    return;
  }

  try {
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Verifying...";
    }

    await verifyRegistration(pendingRegisterEmail, otpCode);
    showToast("Account verified successfully! Logging you in...", "success");

    // Perform auto-login with pending credentials
    if (pendingRegisterEmail && pendingRegisterPassword) {
      try {
        await login(pendingRegisterEmail, pendingRegisterPassword);
      } catch (err) {
        // Ignore auto-login error if cookie was already set
      }
    }

    setTimeout(() => {
      window.location.href = "dashboard.html";
    }, 800);

  } catch (error) {
    showToast(error.message || "Invalid OTP code. Please try again.", "error");
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Verify Account";
    }
  }
}

async function handleResendOtp() {
  const resendBtn = document.getElementById("resendOtpBtn");
  if (!pendingRegisterEmail) {
    showToast("No email associated with pending registration.", "error");
    return;
  }

  try {
    if (resendBtn) {
      resendBtn.disabled = true;
      resendBtn.textContent = "Sending...";
    }
    const res = await resendOTP(pendingRegisterEmail);
    showToast(res.message || "Verification OTP has been resent to your email.", "info");
  } catch (error) {
    showToast(error.message || "Failed to resend OTP.", "error");
  } finally {
    if (resendBtn) {
      resendBtn.disabled = false;
      resendBtn.textContent = "📩 Resend OTP";
    }
  }
}

