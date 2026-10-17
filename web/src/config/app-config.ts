import packageJson from "../../package.json";

const currentYear = new Date().getFullYear();

export const APP_CONFIG = {
  name: "WSARTEX",
  version: packageJson.version,
  copyright: `© ${currentYear}, WSARTEX.`,
  meta: {
    title: "WSARTEX",
    description: "LLM 驱动的自主渗透测试系统控制台",
  },
};
