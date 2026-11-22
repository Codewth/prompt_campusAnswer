from app.official_index import build_official_index


if __name__ == "__main__":
    count = build_official_index()
    print(f"Indexed {count} official-source chunks into the local SQLite TF-IDF vector index.")
