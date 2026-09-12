/** @type {import('tailwindcss').Config} */
module.exports = {
  // 扫描控制台页面与 TS（TS 中的模板字符串里含 badge/font-mono 等类名）
  content: ["../app/static/index.html", "src/**/*.ts"],
  theme: { extend: {} },
  plugins: [require("daisyui")],
  daisyui: {
    // 自定义深色主题，沿用原控制台配色
    themes: [
      {
        adblocker: {
          primary: "#4f8cff",
          "primary-content": "#0b1220",
          secondary: "#3dd68c",
          "secondary-content": "#0b1220",
          accent: "#4f8cff",
          "accent-content": "#0b1220",
          neutral: "#1a2336",
          "neutral-content": "#e8eefc",
          "base-100": "#0b1220",
          "base-200": "#121a2b",
          "base-300": "#243049",
          "base-content": "#e8eefc",
          info: "#4f8cff",
          success: "#3dd68c",
          warning: "#ffc857",
          error: "#ff6b6b",
          "--rounded-box": "1rem",
          "--rounded-btn": "0.5rem",
        },
      },
    ],
    logs: false,
  },
};
