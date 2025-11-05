import express from "express";
import cors from "cors";

const app = express();
app.use(cors());
app.use(express.json());

app.post("/chat", (req, res) => {
  const userMessage = req.body.message;
  res.json({
    reply: `🤖 (Mock) 당신이 말한 내용은: "${userMessage}" 입니다. AWS/Gemini 연결하면 여기가 진짜 결과로 바뀝니다.`
  });
});

app.listen(3001, () => console.log("✅ Mock Server Running at http://localhost:3001"));
