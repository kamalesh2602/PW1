from app.agent.llm import get_llm


def main():
    llm = get_llm()

    response = llm.invoke(
        "Explain what a ZeroDivisionError is in one sentence."
    )

    print(response.content)


if __name__ == "__main__":
    main()