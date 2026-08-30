import asyncio
import time
import unicodedata

from ai_learning.multi_mcp_agent import (
    AgentRuntime,
    ModelClient,
    connect_mcp_servers,
    register_mcp_tools,
)
from ai_learning.config import load_settings
from ai_learning.providers.factory import create_provider

from ai_learning.evaluation.cases import EVALUATION_CASES

def normalize_text(text):
    text = unicodedata.normalize("NFKC", text)

    for char in "\u2010\u2011\u2012\u2013\u2014\u2212":
        text = text.replace(char, "-")

    text = " ".join(text.split())

    return text.lower()

def check_expected_facts(answer, expected_facts):
    if not answer:
        return False, expected_facts

    answer_normalized = normalize_text(answer)

    missing_facts = [
        fact
        for fact in expected_facts
        if normalize_text(fact) not in answer_normalized
    ]

    return len(missing_facts) == 0, missing_facts

async def run_evaluations():
    settings = load_settings()

    mcp_servers = {
        "weather": settings.weather_mcp_url,
        "kubernetes": settings.kubernetes_mcp_url,
    }

    async with connect_mcp_servers(mcp_servers) as connections:
        tool_registry = {}
        llm_tools = []

        for connection in connections.values():
            register_mcp_tools(
                connection,
                tool_registry,
                llm_tools,
            )

        try:
            provider = create_provider()
            model_client = ModelClient(
                provider=provider,
            )
        except Exception as exc:
            print("\nEVALUATION SETUP ERROR:")
            print(f"{type(exc).__name__}: {exc}")
            return

        results = []

        for case in EVALUATION_CASES:
            print(f"\n--- EVALUATION: {case.name} ---")
            print(f"PROMPT: {case.prompt}")

            runtime = AgentRuntime(
                model_client=model_client,
                llm_tools=llm_tools,
                tool_registry=tool_registry,
            )

            try:
                start_time = time.perf_counter()

                answer = await runtime.run(case.prompt)

                elapsed = time.perf_counter() - start_time

                executed_tools = runtime.state.executed_tools
                iterations = runtime.state.iterations

                tool_selection_passed = set(case.expected_tools).issubset(
                    set(executed_tools)
                )

                answer_passed, missing_facts = check_expected_facts(
                    answer,
                    case.expected_facts,
                )

                passed = tool_selection_passed and answer_passed

                results.append(
                    {
                        "name": case.name,
                        "expected_tools": case.expected_tools,
                        "executed_tools": executed_tools,
                        "iterations": iterations,
                        "passed": passed,
                        "tool_selection_passed": tool_selection_passed,
                        "answer_passed": answer_passed,
                        "missing_facts": missing_facts,
                        "status": "PASS" if passed else "FAIL",
                        "answer": answer,
                    }
                )

                print("\nEVALUATION RESULT:")
                print(f"Expected tools: {case.expected_tools}")
                print(f"Executed tools: {executed_tools}")
                print(f"Iterations: {iterations}")
                print(f"Latency: {elapsed:.2f}s")
                print(
                    f"Tool selection: "
                    f"{'PASS' if tool_selection_passed else 'FAIL'}"
                )
                print(
                    f"Answer correctness: "
                    f"{'PASS' if answer_passed else 'FAIL'}"
                )

                if missing_facts:
                    print(f"Missing facts: {missing_facts}")

                print(f"Result: {'PASS' if passed else 'FAIL'}")
                
            except Exception as exc:
                results.append(
                    {
                        "name": case.name,
                        "expected_tools": case.expected_tools,
                        "executed_tools": runtime.state.executed_tools,
                        "iterations": runtime.state.iterations,
                        "passed": False,
                        "tool_selection_passed": False,
                        "answer_passed": False,
                        "missing_facts": [],
                        "status": "ERROR",
                        "answer": None,
                        "error": str(exc),
                    }
                )

                print("\nEVALUATION ERROR:")
                print(f"{type(exc).__name__}: {exc}")

        passed_count = sum(
            result["status"] == "PASS"
            for result in results
        )

        average_iterations = sum(
            result["iterations"]
            for result in results
        ) / len(results)

        tool_selection_pass_count = sum(
            result["tool_selection_passed"]
            for result in results
        )

        answer_correctness_pass_count = sum(
            result["answer_passed"]
            for result in results
        )

        tool_selection_accuracy = (
            tool_selection_pass_count / len(results)
        )

        answer_correctness_accuracy = (
            answer_correctness_pass_count / len(results)
        )

        print(f"Tool selection accuracy: {tool_selection_accuracy:.0%}")
        print(f"Average iterations: {average_iterations:.2f}")

        print("\n====================")
        print("EVALUATION SUMMARY")
        print("====================")

        for result in results:
            print(
                f"{result['name']}: "
                f"{result['status']}"
            )
        
        print(
            f"\nScore: {passed_count}/{len(results)}"
        )
        print(
            f"Tool selection accuracy: "
            f"{tool_selection_accuracy:.0%}"
        )

        print(
            f"Answer correctness: "
            f"{answer_correctness_accuracy:.0%}"
        )

        print(
            f"Average iterations: "
            f"{average_iterations:.2f}"
        )


if __name__ == "__main__":
    asyncio.run(run_evaluations())