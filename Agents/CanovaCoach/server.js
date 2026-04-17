const express = require('express');
const cors = require('cors');
const { GoogleGenerativeAI } = require("@google/generative-ai");
const fs = require('fs');
const path = require('path');
require('dotenv').config();

const app = express();
app.use(cors()); // 允许 Vercel 前端跨域访问
app.use(express.json());

// 初始化 Gemini
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = genAI.getGenerativeModel({ model: "gemini-1.5-pro" });

// 读取思想矿石 — 使用 __dirname 确保路径在任何 CWD 下都正确
const canovaKnowledge = fs.readFileSync(path.join(__dirname, 'canova_raw.md'), 'utf8');

app.post('/api/coach/analyze', async (req, res) => {
    const { runData } = req.body;

    const prompt = `
        你现在是顶级教练 Renato Canova。
        你的核心哲学：${canovaKnowledge}
        Alex 的最新跑步数据：${JSON.stringify(runData)}
        请根据数据给出 Canova 风格的点评。
    `;

    try {
        const result = await model.generateContent(prompt);
        const advice = result.response.text();
        res.json({ success: true, advice });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🚀 RGM Backend running on port ${PORT}`));
