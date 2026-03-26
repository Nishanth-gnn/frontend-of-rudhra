import time
from ddgs import DDGS


def web_search(query, max_results=5):
    try:
        start_time = time.time()

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        latency = time.time() - start_time
        return results, latency

    except Exception as e:
        return str(e), 0


def evaluate_results(results):
    if not results or isinstance(results, str):
        return "❌ No valid results"

    total = len(results)
    avg_len = sum(len(r.get("body", "")) for r in results) / total

    quality = "Good" if avg_len > 80 else "Low"

    return f"""
📊 Evaluation:
- Total Results: {total}
- Avg Content Length: {int(avg_len)}
- Quality: {quality}
"""


def main():
    print("\n🔍 DuckDuckGo Tester (Fixed)")
    print("-" * 40)

    query = input("Enter your query: ")

    results, latency = web_search(query)

    print(f"\n⏱️ Response Time: {round(latency, 3)} sec")

    if isinstance(results, str):
        print("Error:", results)
        return

    if not results:
        print("❌ No results found")
        return

    print("\n📌 Results:\n")

    for i, r in enumerate(results, 1):
        title = r.get("title", "No Title")
        body = r.get("body", "No description")
        link = r.get("href", "No link")

        print(f"{i}. {title}")
        print(f"   {body[:200]}...")
        print(f"   🔗 {link}")
        print("-" * 50)

    print(evaluate_results(results))


if __name__ == "__main__":
    main()