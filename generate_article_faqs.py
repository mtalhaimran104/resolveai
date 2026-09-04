import requests

from knowledge.models import KnowledgeArticle
from knowledge.models import KnowledgeArticleFAQ


def main():
    articles = KnowledgeArticle.objects.all()

    print("Articles:", articles.count())

    for article in articles:
        try:
            prompt = f"{article.title}\n\n{article.content}"

            response = requests.post(
                "http://ai_service:8001/student-query/",
                json={"question": prompt},
                timeout=60,
            )

            print(
                f"\nARTICLE: {article.title}"
                f"\nSTATUS: {response.status_code}"
            )

            if not response.ok:
                print("FAILED:", response.text[:300])
                continue

            data = response.json()

            answer = (
                data.get("answer")
                or data.get("response")
                or data.get("suggested_answer")
            )

            if not answer:
                print("NO ANSWER")
                continue

            KnowledgeArticleFAQ.objects.create(
                article=article,
                question=article.title,
                answer=answer,
                confidence_score=data.get("similarity_score"),
                model_name=data.get("model", ""),
                model_version=data.get("model_version", ""),
            )

            print("SAVED")

        except Exception as exc:
            print("ERROR:", str(exc))

    print(
        "\nTotal Article FAQs:",
        KnowledgeArticleFAQ.objects.count(),
    )


main()