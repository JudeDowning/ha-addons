from backend.core.famly_client import FamlyClient


def test_clean_detail_lines_removes_icon_labels_and_title_duplicates():
    client = FamlyClient(email="test@example.com", password="secret")

    lines = client._clean_detail_lines(
        [
            "logout",
            "Garden",
            "16:21 - 17:15",
            "16:21 - 17:15",
            "info",
            "  ",
        ],
        title_text="Garden",
    )

    assert lines == ["16:21 - 17:15"]


def test_split_entry_blocks_groups_meal_items_by_time():
    client = FamlyClient(email="test@example.com", password="secret")

    blocks = client._split_entry_blocks(
        [
            "16:04 Tea",
            "Fishcake and beans (All)",
            "11:30 Lunch",
            "Chicken curry (All)",
        ]
    )

    assert blocks == [
        ["16:04 Tea", "Fishcake and beans (All)"],
        ["11:30 Lunch", "Chicken curry (All)"],
    ]
