"""
Temporal utilities for generating rich timestamp metadata.
Handles conversion of timestamps to detailed temporal information for enhanced searching.
"""

import logging
from datetime import datetime
from typing import Any

from inmemory.common.constants import TemporalConstants

logger = logging.getLogger(__name__)


class TemporalProcessor:
    """
    Processes timestamps into rich temporal metadata structures.
    Follows Uncle Bob's Single Responsibility Principle.
    """

    @staticmethod
    def generate_temporal_metadata(timestamp: datetime = None) -> dict[str, Any]:
        """
        Generate comprehensive temporal metadata from a timestamp.

        Args:
            timestamp: DateTime object, defaults to current time if None

        Returns:
            Dictionary containing rich temporal information

        Raises:
            ValueError: If timestamp is invalid
            Exception: If temporal processing fails
        """
        try:
            if timestamp is None:
                timestamp = datetime.now()

            if not isinstance(timestamp, datetime):
                raise ValueError("Timestamp must be a datetime object")

            # Calculate day of year
            day_of_year = timestamp.timetuple().tm_yday

            # Calculate week of year (ISO week)
            week_of_year = timestamp.isocalendar()[1]

            # Determine quarter
            quarter = TemporalProcessor._get_quarter(timestamp.month)

            # Check if weekend
            is_weekend = timestamp.weekday() >= 5  # Saturday=5, Sunday=6

            # Get day of week name
            day_of_week = TemporalConstants.WEEKDAYS[timestamp.weekday()]

            temporal_data = {
                "day": timestamp.day,
                "hour": timestamp.hour,
                "year": timestamp.year,
                "month": timestamp.month,
                "minute": timestamp.minute,
                "quarter": quarter,
                "is_weekend": is_weekend,
                "day_of_week": day_of_week,
                "day_of_year": day_of_year,
                "week_of_year": week_of_year,
            }

            logger.debug(f"Generated temporal metadata: {temporal_data}")
            return temporal_data

        except Exception as e:
            logger.error(f"Failed to generate temporal metadata: {str(e)}")
            raise Exception(f"Temporal processing failed: {str(e)}") from e

    @staticmethod
    def _get_quarter(month: int) -> int:
        """
        Determine quarter from month number.

        Args:
            month: Month number (1-12)

        Returns:
            Quarter number (1-4)
        """
        for quarter, months in TemporalConstants.QUARTERS.items():
            if month in months:
                return quarter
        return 1  # Default fallback

    @staticmethod
    def parse_temporal_query(query: str) -> dict[str, Any]:
        """
        Parse natural language temporal queries into filter conditions.

        Args:
            query: Natural language query like "yesterday", "last week", etc.

        Returns:
            Dictionary with temporal filter conditions
        """
        query_lower = query.lower().strip()
        current_time = datetime.now()

        filters = {}

        try:
            if query_lower == "today":
                filters["day"] = current_time.day
                filters["month"] = current_time.month
                filters["year"] = current_time.year

            elif query_lower == "yesterday":
                yesterday = datetime.now().replace(day=current_time.day - 1)
                filters["day"] = yesterday.day
                filters["month"] = yesterday.month
                filters["year"] = yesterday.year

            elif query_lower == "this_week":
                filters["week_of_year"] = current_time.isocalendar()[1]
                filters["year"] = current_time.year

            elif query_lower == "weekends":
                filters["is_weekend"] = True

            elif query_lower == "weekdays":
                filters["is_weekend"] = False

            elif query_lower in TemporalConstants.WEEKDAYS:
                filters["day_of_week"] = query_lower

            elif query_lower.startswith("q") and len(query_lower) == 2:
                try:
                    quarter_num = int(query_lower[1])
                    if 1 <= quarter_num <= 4:
                        filters["quarter"] = quarter_num
                except ValueError:
                    pass

            elif query_lower in ["morning", "am"]:
                filters["hour_range"] = (6, 12)

            elif query_lower in ["afternoon", "pm"]:
                filters["hour_range"] = (12, 18)

            elif query_lower in ["evening", "night"]:
                filters["hour_range"] = (18, 23)

            logger.debug(f"Parsed temporal query '{query}' to filters: {filters}")
            return filters

        except Exception as e:
            logger.warning(f"Failed to parse temporal query '{query}': {str(e)}")
            return {}


class TemporalFilter:
    """
    Handles temporal filtering operations for memory search.
    Clean separation of concerns from TemporalProcessor.
    """

    @staticmethod
    def build_temporal_conditions(filters: dict[str, Any]) -> dict[str, Any]:
        """
        Build Qdrant filter conditions from temporal filters.

        Args:
            filters: Dictionary of temporal filter conditions

        Returns:
            Qdrant-compatible filter conditions
        """
        conditions = []

        try:
            for field, value in filters.items():
                if field == "hour_range":
                    # Handle hour range filtering
                    start_hour, end_hour = value
                    conditions.append(
                        {
                            "key": "temporal.hour",
                            "range": {"gte": start_hour, "lt": end_hour},
                        }
                    )
                else:
                    # Handle exact matches
                    conditions.append(
                        {"key": f"temporal.{field}", "match": {"value": value}}
                    )

            return {"must": conditions} if conditions else {}

        except Exception as e:
            logger.error(f"Failed to build temporal conditions: {str(e)}")
            return {}


if __name__ == "__main__":
    # Test temporal processing
    processor = TemporalProcessor()

    # Test current time
    temporal_data = processor.generate_temporal_metadata()
    print(f"Current temporal data: {temporal_data}")

    # Test query parsing
    test_queries = ["today", "yesterday", "weekends", "q3", "morning"]
    for query in test_queries:
        filters = processor.parse_temporal_query(query)
        print(f"Query '{query}' -> Filters: {filters}")
