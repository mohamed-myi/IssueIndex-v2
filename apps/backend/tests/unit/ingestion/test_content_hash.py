

from gim_backend.ingestion.content_hash import compute_content_hash


class TestContentHash:
    def test_hash_matches_known_output(self):
        assert (
            compute_content_hash("I_123", "Bug report", "Description")
            == "56deae1f9857c5766cb6e34463d8697b48fffe350935a94784c85c9d6902f325"
        )

    def test_hash_changes_when_content_changes(self):
        base = compute_content_hash("I_123", "Bug report", "Description")

        assert compute_content_hash("I_124", "Bug report", "Description") != base
        assert compute_content_hash("I_123", "Bug fix", "Description") != base
        assert compute_content_hash("I_123", "Bug report", "New description") != base
