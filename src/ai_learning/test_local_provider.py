from ai_learning.providers.factory import create_provider


def main():
    provider = create_provider()

    response = provider.chat(
        messages=[
            {
                "role": "user",
                "content": "Explain what an API is in one sentence.",
            }
        ],
        tools=[],
    )

    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()