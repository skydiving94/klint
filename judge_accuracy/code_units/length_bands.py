"""The bands of length the units of the code-unit set are scored in."""

from dataclasses import dataclass

# The budget every judge had before any was measured; the margin compares
# each band above it with the units below it.
BASELINE_LENGTH = 2_000


@dataclass(frozen=True)
class LengthBand:
    """The units at least lower_length and below upper_length characters long."""

    lower_length: int
    upper_length: int

    def does_hold(self, length: int) -> bool:
        return self.lower_length <= length < self.upper_length

    def is_below_baseline(self) -> bool:
        return self.upper_length <= BASELINE_LENGTH

    def describe(self) -> str:
        return f"{self.lower_length:,} to {self.upper_length - 1:,}"


# Finer near the baseline, where a budget is most likely to stop.
LENGTH_BANDS: tuple[LengthBand, ...] = (
    LengthBand(0, 1_000),
    LengthBand(1_000, 2_000),
    LengthBand(2_000, 3_000),
    LengthBand(3_000, 4_000),
    LengthBand(4_000, 6_000),
    LengthBand(6_000, 8_000),
    LengthBand(8_000, 12_000),
)
