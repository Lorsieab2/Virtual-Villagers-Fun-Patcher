import unittest

from tools.parentage_log import (
    BirthCard,
    Person,
    parentage_log_filename,
    parentage_log_path,
    render_parentage_html,
)


class ParentageLogSharedFormatTests(unittest.TestCase):
    def test_filename_and_location_are_stable(self) -> None:
        title = "Virtual Villagers - The Tree of Life"
        self.assertEqual(
            parentage_log_filename(title),
            "Virtual Villagers - The Tree of Life Parentage Log.html",
        )
        self.assertEqual(
            parentage_log_path(r"C:\\Modded", title),
            __import__("pathlib").Path(
                r"C:\\Modded\\Virtual Villagers - The Tree of Life Parentage Log.html"
            ),
        )

    def test_same_format_accepts_each_game_title(self) -> None:
        person = Person("A", 0, 0, 0)
        card = BirthCard(person, person, person)
        for title in (
            "Virtual Villagers - A New Home",
            "Virtual Villagers - The Lost Children",
            "Virtual Villagers - The Secret City",
            "Virtual Villagers - The Tree of Life",
            "Virtual Villagers - New Believers",
        ):
            with self.subTest(title=title):
                html = render_parentage_html([card], game_title=title)
                self.assertIn(f"{title} Parentage Log", html)
                self.assertIn(
                    "head and body values correspond to the rows in the Body and Head pictures in the Images folder.",
                    html,
                )


if __name__ == "__main__":
    unittest.main()
