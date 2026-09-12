"""
Lab #3: Baseline Chatbot vs ReAct Agent
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from tools import TOOL_DEFINITIONS, TOOL_MAP


SYSTEM_PROMPT = """Bạn là một ReAct Agent thông minh hỗ trợ khách hàng Vingroup.
Bạn chỉ sử dụng các công cụ sau:
{tools}

Quy trình trả lời bắt buộc:
Thought: <Suy nghĩ bước tiếp theo>
Action: {{"name": "<tên tool>", "args": {{<tham số>}}}}
Observation: <Kết quả từ tool>
... (Lặp lại cho tới khi có đủ dữ liệu)
Final Answer: <Câu trả lời hoàn chỉnh cho khách hàng>
"""


class ChatbotBaseline:
    """Baseline Chatbot không sử dụng tool hay ReAct loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        return {
            "status": "success",
            "answer": (
                "Tôi là chatbot cơ bản nên chưa thể tra cứu dữ liệu chuyến bay "
                "hoặc thời tiết theo thời gian thực."
            ),
            "tool_calls": [],
        }


class ReActAgent:
    """ReAct Agent sử dụng Thought - Action - Observation loop."""

    AIRPORT_CODES = {"HAN", "SGN", "DAD"}

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def _extract_budget(self, user_input: str) -> int:
        """Trích xuất mức giá tối đa từ câu hỏi, mặc định là 5 triệu VND."""
        normalized = user_input.casefold()

        match = re.search(
            r"(?:dưới|duoi|<|tối đa|toi da|không quá|khong qua)\s*"
            r"(\d+(?:[.,]\d+)*)\s*"
            r"(triệu|trieu|tr|k|nghìn|nghin|vnd|đ|d)?",
            normalized,
        )

        if not match:
            return 5_000_000

        raw_value, unit = match.groups()
        unit = unit or ""

        try:
            if unit in {"triệu", "trieu", "tr"}:
                value = float(raw_value.replace(",", "."))
                return int(value * 1_000_000)

            if unit in {"k", "nghìn", "nghin"}:
                value = float(raw_value.replace(",", "."))
                return int(value * 1_000)

            value = int(raw_value.replace(".", "").replace(",", ""))

            # Ví dụ: “dưới 2” thường được hiểu là dưới 2 triệu VND.
            return value * 1_000_000 if value < 1_000 else value
        except ValueError:
            return 5_000_000

    def _extract_request(self, user_input: str) -> List[Dict[str, Any]]:
        """Tạo danh sách Action cần thực hiện từ câu hỏi của người dùng."""
        normalized = user_input.casefold()
        codes = re.findall(r"\b(HAN|SGN|DAD)\b", user_input.upper())
        actions: List[Dict[str, Any]] = []

        mentions_flight = bool(
            re.search(
                r"\b(chuyến bay|chuyen bay|vé máy bay|ve may bay|flight|vé|ve)\b",
                normalized,
            )
        )

        # Chỉ tìm chuyến bay nếu xác định được đủ điểm đi và điểm đến.
        if mentions_flight and len(codes) >= 2:
            actions.append(
                {
                    "name": "get_flight_info",
                    "args": {
                        "origin": codes[0],
                        "destination": codes[1],
                        "max_price": self._extract_budget(user_input),
                    },
                }
            )

        mentions_weather = bool(
            re.search(
                r"thời tiết|thoi tiet|weather|mặc gì|mac gi|trang phục|trang phuc|nên mặc|nen mac",
                normalized,
            )
        )

        if mentions_weather:
            weather_code: Optional[str] = None

            weather_match = re.search(
                r"(?:thời tiết|thoi tiet|weather).*?\b(HAN|SGN|DAD)\b",
                user_input,
                flags=re.IGNORECASE,
            )
            if weather_match:
                weather_code = weather_match.group(1).upper()
            elif "đà nẵng" in normalized or "da nang" in normalized:
                weather_code = "DAD"
            elif "hà nội" in normalized or "ha noi" in normalized:
                weather_code = "HAN"
            elif (
                "hồ chí minh" in normalized
                or "ho chi minh" in normalized
                or "sài gòn" in normalized
                or "sai gon" in normalized
            ):
                weather_code = "SGN"
            elif codes:
                weather_code = codes[-1]

            if weather_code:
                actions.append(
                    {
                        "name": "get_weather_forecast",
                        "args": {"city_code": weather_code},
                    }
                )

        return actions

    def _call_tool(self, raw_action: str) -> Tuple[Dict[str, Any], Any]:
        """
        Parse Action JSON và gọi tool tương ứng.
        Trả về action đã chuẩn hoá cùng Observation.
        """
        try:
            action = json.loads(raw_action)
        except json.JSONDecodeError:
            return {}, {"error": "Invalid JSON format"}

        if not isinstance(action, dict):
            return {}, {"error": "Invalid JSON format"}

        tool_name = str(action.get("name", "")).strip().lower()
        tool_args = action.get("args", {})

        if not isinstance(tool_args, dict):
            return {}, {"error": "Tool arguments must be a JSON object"}

        if tool_name not in TOOL_MAP:
            return (
                {"name": tool_name, "args": tool_args},
                {"error": f"Tool '{tool_name}' not found"},
            )

        try:
            observation = TOOL_MAP[tool_name](**tool_args)
        except TypeError as error:
            observation = {"error": f"Invalid tool arguments: {error}"}
        except Exception as error:
            observation = {"error": f"Tool execution failed: {error}"}

        return {"name": tool_name, "args": tool_args}, observation

    def _build_answer(self, observations: Dict[str, Any]) -> str:
        """Tạo Final Answer từ các Observation nhận được."""

        flight_result = observations.get("get_flight_info")
        weather_result = observations.get("get_weather_forecast")
        answer_parts: List[str] = []

        if flight_result is not None:
            if isinstance(flight_result, list) and flight_result:
                flight_text = []
                for flight in flight_result:
                    price = f"{flight['price_vnd']:,}".replace(",", ".")
                    flight_text.append(
                        f"{flight['flight_number']} ({flight['airline']}) "
                        f"khởi hành {flight['departure_time']}, giá {price} VND"
                    )

                answer_parts.append(
                    "Các chuyến bay phù hợp: " + "; ".join(flight_text) + "."
                )
            else:
                answer_parts.append(
                    "Hiện chưa tìm thấy chuyến bay phù hợp với điều kiện của bạn."
                )

        if weather_result is not None:
            if isinstance(weather_result, dict) and "error" not in weather_result:
                answer_parts.append(
                    f"Thời tiết tại {weather_result['city']}: "
                    f"{weather_result['temperature_c']}°C, "
                    f"{weather_result['condition']}, "
                    f"độ ẩm {weather_result['humidity_pct']}%. "
                    f"Gợi ý trang phục: {weather_result['recommendation']}"
                )
            else:
                error_message = (
                    weather_result.get("error", "Không có dữ liệu thời tiết")
                    if isinstance(weather_result, dict)
                    else "Không có dữ liệu thời tiết"
                )
                answer_parts.append(f"Không thể tra cứu thời tiết: {error_message}.")

        if not answer_parts:
            return (
                "Vinpearl khuyến nghị bạn kiểm tra chính sách đổi hoặc hoàn vé "
                "trên kênh hỗ trợ chính thức, vì điều kiện có thể thay đổi theo "
                "loại vé và thời điểm đặt vé."
            )

        return " ".join(answer_parts)

    def _max_iterations_result(self) -> Dict[str, Any]:
        return {
            "status": "max_iterations_reached",
            "answer": "Không thể hoàn thành trong số bước tối đa.",
            "iterations": len(self.trace),
            "trace": self.trace,
        }

    def run(self, user_input: str) -> Dict[str, Any]:
        """Chạy Thought - Action - Observation loop."""
        self.trace = []

        if self.max_iterations <= 0:
            return self._max_iterations_result()

        actions = self._extract_request(user_input)
        observations: Dict[str, Any] = {}

        # Câu hỏi FAQ không cần tool.
        if not actions:
            answer = self._build_answer(observations)
            self.trace.append(
                {
                    "iteration": 1,
                    "thought": "Câu hỏi không yêu cầu tra cứu dữ liệu bằng tool.",
                    "action": None,
                    "observation": None,
                    "final_answer": answer,
                }
            )
            return {
                "status": "completed",
                "answer": answer,
                "iterations": 1,
                "trace": self.trace,
            }

        for index, planned_action in enumerate(actions, start=1):
            if index > self.max_iterations:
                return self._max_iterations_result()

            raw_action = json.dumps(planned_action, ensure_ascii=False)
            action, observation = self._call_tool(raw_action)

            tool_name = action.get("name", "unknown_tool")
            observations[tool_name] = observation

            trace_item = {
                "iteration": index,
                "thought": f"Cần dùng {tool_name} để lấy thông tin cần thiết.",
                "action": action,
                "observation": observation,
            }
            self.trace.append(trace_item)

            # Với câu hỏi chỉ cần một tool, trả lời ngay trong vòng lặp đầu tiên.
            if len(actions) == 1:
                answer = self._build_answer(observations)
                trace_item["final_answer"] = answer
                return {
                    "status": "completed",
                    "answer": answer,
                    "iterations": index,
                    "trace": self.trace,
                }

        # Trường hợp nhiều tool cần thêm một bước để tổng hợp Final Answer.
        if len(self.trace) >= self.max_iterations:
            return self._max_iterations_result()

        answer = self._build_answer(observations)
        self.trace.append(
            {
                "iteration": len(self.trace) + 1,
                "thought": "Đã có đủ dữ liệu, tổng hợp câu trả lời cho khách hàng.",
                "action": None,
                "observation": observations,
                "final_answer": answer,
            }
        )

        return {
            "status": "completed",
            "answer": answer,
            "iterations": len(self.trace),
            "trace": self.trace,
        }


def main():
    user_query = (
        "Tìm cho tôi chuyến bay từ HAN đi SGN dưới 2 triệu, "
        "rồi cho biết thời tiết SGN nên mặc gì?"
    )

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING REACT AGENT ===")
    agent = ReActAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result)
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()