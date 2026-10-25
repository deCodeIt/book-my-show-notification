import sys


class Selector:
    """Interactive selection of a region or venue from a list.

    Isolated from the data/network layer so UI behaviour can change or be
    replaced (e.g. with a TUI) without touching the rest of the program.
    """

    def choose_region(self, regions):
        return self._choose(
            regions,
            empty_message="No regions found",
            prompt="Enter the regions number of your choice (or 'q' to quit): ",
            display=lambda region: f"{region.RegionCode}: {region.RegionName}",
        )

    def choose_venue(self, venues):
        return self._choose(
            venues,
            empty_message="No venues found",
            prompt="Enter the venue number of your choice (or 'q' to quit): ",
            display=lambda venue: f"{venue.VenueCode}: {venue.VenueName}",
        )

    def _choose(self, items, empty_message, prompt, display):
        if len(items) == 0:
            print(empty_message)
            sys.exit(1)
        while True:
            for index, item in enumerate(items, start=1):
                print(f"{index}. {display(item)}")
            choice = input(prompt)
            if choice.lower() == "q":
                sys.exit(1)
            try:
                choice_index = int(choice)
                if 1 <= choice_index <= len(items):
                    return items[choice_index - 1]
                print("Invalid choice. Please enter a valid number.")
            except ValueError:
                print("Invalid input. Please enter a number or 'q' to quit.")
