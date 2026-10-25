"""Log rotation keeps the shared log bounded. No network."""

from shop.logfile import append_line


def test_rotation_starts_a_new_file_when_the_limit_is_reached(tmp_path):
    log = tmp_path / "shop.log"
    for i in range(5):
        append_line(log, f"line-{i}\n" * 10, max_bytes=100, backups=3)
    assert log.exists()
    assert log.with_name("shop.log.1").exists()
    assert log.stat().st_size <= 100 + len("line-0\n" * 10)


def test_only_the_configured_number_of_backups_is_kept(tmp_path):
    log = tmp_path / "shop.log"
    for i in range(20):
        append_line(log, f"entry {i:02d} " + "x" * 40 + "\n", max_bytes=60, backups=2)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["shop.log", "shop.log.1", "shop.log.2"]


def test_newest_lines_are_in_the_current_file(tmp_path):
    log = tmp_path / "shop.log"
    for i in range(10):
        append_line(log, f"entry {i}\n", max_bytes=30, backups=3)
    assert log.read_text(encoding="utf-8").strip().endswith("entry 9")


def test_no_rotation_when_backups_is_zero(tmp_path):
    log = tmp_path / "shop.log"
    for i in range(10):
        append_line(log, "x" * 50 + "\n", max_bytes=10, backups=0)
    assert [p.name for p in tmp_path.iterdir()] == ["shop.log"]
