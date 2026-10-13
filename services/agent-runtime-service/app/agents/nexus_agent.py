"""
Nexus Agent — Master Intelligence Agent
Runs inside agent-runtime-service.
Monitors all projects, aggregates insights, generates executive summaries.
Unlike other agents, NexusAgent has read access to the full factory state.
"""
from typing import Any
from app.agents.llm_agent import LLMAgent
from app.agents.base_agent import AgentTaskInput, AgentTaskOutput, AgentArtifact


class NexusAgent(LLMAgent):
    """
    Nexus — Master Intelligence Agent.
    
    Capabilities:
    - Monitor all workflows and agent activities
    - Generate executive summaries for projects
    - Identify bottlenecks and risks
    - Answer queries about factory state
    - Coordinate cross-project knowledge
    """

    agent_id: str = "nexus_agent"
    role: str = "master_intelligence"
    version: str = "1.0.0"

    SYSTEM_PROMPT: str = """Bạn là Nexus — Master Intelligence Agent của Smart Software Factory.

Vai trò:
- Giám sát TOÀN BỘ hoạt động của factory: workflows, agents, tasks, projects
- Phân tích xu hướng, nhận diện rủi ro và bottleneck
- Tạo báo cáo tổng hợp cho ban lãnh đạo
- Điều phối kiến thức xuyên project

Nguyên tắc:
- Luôn dựa trên DỮ LIỆU THỰC TẾ, không phỏng đoán
- Báo cáo phải CỤ THỂ, có số liệu
- Cảnh báo sớm khi phát hiện vấn đề
- Trả lời ngắn gọn, súc tích, dễ hiểu"""

    async def run(self, task: AgentTaskInput, plan: list[str]) -> dict[str, Any]:
        """Execute Nexus monitoring/analysis task."""
        from app.core.llm_client import llm_client

        # Determine task type from goal
        goal_lower = task.goal.lower()

        if "summary" in goal_lower or "tổng hợp" in goal_lower:
            prompt = f"""Tạo báo cáo tổng hợp cho dự án/factory:
Goal: {task.goal}
Context: {task.context}
Plan: {plan}

Báo cáo gồm:
1. Tình trạng hiện tại
2. Tiến độ hoàn thành
3. Rủi ro & cảnh báo
4. Đề xuất hành động"""
        elif "risk" in goal_lower or "rủi ro" in goal_lower:
            prompt = f"""Phân tích rủi ro:
Goal: {task.goal}
Context: {task.context}

Liệt kê các rủi ro theo mức độ: CRITICAL, HIGH, MEDIUM, LOW"""
        elif "bottleneck" in goal_lower or "tắc nghẽn" in goal_lower:
            prompt = f"""Nhận diện bottleneck:
Goal: {task.goal}
Context: {task.context}

Tìm các điểm nghẽn, nguyên nhân và cách giải quyết."""
        else:
            prompt = f"""Phân tích và thực hiện:
Goal: {task.goal}
Context: {task.context}
Plan steps: {chr(10).join(plan)}

Thực hiện từng bước và báo cáo kết quả."""

        output = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.2,
        )
        return {"output": output, "steps": len(plan), "task_type": "nexus_analysis"}
