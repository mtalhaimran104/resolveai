from app.services.iub_knowledge_service import search_iub_programs


queries = [
    "Does IUB offer cyber security?",
    "Is robotics available?",
    "Does IUB have telecommunication engineering?",
    "What biomedical programs does IUB offer?"
]


for query in queries:

    results, score = search_iub_programs(query)

    print("\nQUERY:")
    print(query)

    print("BEST SIMILARITY:")
    print(score)

    print("RESULTS:")

    for result in results:
        print(result)