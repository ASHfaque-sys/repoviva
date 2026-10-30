from repoviva.similarity import jaccard, calculate_edges, score_pair


def repo(name, languages, topics, description, readme):
    return {"full_name": name, "languages": languages, "topics": topics,
            "description": description, "readme_text": readme}


def test_jaccard_exact_overlap():
    assert jaccard(["Python", "SQL"], ["python", "Java"]) == 1 / 3


def test_jaccard_returns_none_when_data_missing():
    assert jaccard([], ["Python"]) is None


def test_pair_score_is_bounded_and_explained():
    a = repo("a/one", ["Python"], ["nlp"], "financial text analysis", "Use Python for text analysis")
    b = repo("b/two", ["Python"], ["nlp"], "financial document classifier", "Text processing pipeline")
    result = score_pair(a, b, 0.25)
    assert 0 <= result["overall_score"] <= 1
    assert result["technology_score"] == 1.0
    assert result["topic_score"] == 1.0
    assert "shared_languages" in result["evidence"]


def test_calculate_edges_all_unique_pairs():
    repos = [
        repo("a/one", ["Python"], ["data"], "data project", "pandas cleaning"),
        repo("b/two", ["Python"], ["ml"], "model project", "scikit learn classifier"),
        repo("c/three", ["Java"], ["backend"], "api server", "spring service"),
    ]
    edges = calculate_edges(repos)
    assert len(edges) == 3
    assert all(0 <= e["overall_score"] <= 1 for e in edges)
