 const { GoogleGenerativeAI } = require("@google/generative-ai");
const fs = require('fs');
const path = require('path');
require('dotenv').config();

// 初始化 Gemini
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = genAI.getGenerativeModel({ model: "gemini-1.5-pro" });

// 读取你手动创建的思想矿石 — 使用 __dirname 确保路径正确
const canovaKnowledge = fs.readFileSync(path.join(__dirname, 'canova_raw.md'), 'utf8');

async function getCoachAdvice(userRunData) {
    const prompt = `
        你现在是顶级教练 Renato Canova。
        核心哲学：
        ${canovaKnowledge}

        待分析数据：
        ${JSON.stringify(userRunData)}

        请根据 Alex 的最新跑步数据，以 Canova 的语气给出简短但毒辣的专业反馈。
        重点关注：这节课是否具有“特异性（Specificity）”？是否是垃圾跑？
    `;

    try {
        const result = await model.generateContent(prompt);
        const response = await result.response;
        console.log("🇮🇹 Renato Canova 说：\n", response.text());
    } catch (error) {
        console.error("❌ Gemini 调用失败:", error);
    }
}

// 模拟 Alex 备赛 Mt. FUJI 100 的一条数据
const latestRun = {
    date: "2026-04-16",
    distance: "25km",
    elevation: "1500m",
    avg_pace: "9:30 min/km",
    description: "在云南大理进行的慢速爬坡练习，感觉心率很平稳。"
};

getCoachAdvice(latestRun);
