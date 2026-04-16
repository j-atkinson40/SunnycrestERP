"""Import Intelligence Service — analytics and insights from import data.

NEW: intelligence layer for import data analysis. Generates business summaries,
pricing history, and seasonal patterns from imported historical data.
"""

import logging
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Product

logger = logging.getLogger(__name__)


class ImportIntelligenceService:
    """Analyzes import data to generate business intelligence summaries."""

    @staticmethod
    def generate_business_summary(
        raw_data: list[dict],
        column_mapping: dict,
        company_id: str,
        db: Session,
    ) -> dict:
        """Analyze import data to produce a business overview.

        Returns: date_range, total_orders, total_revenue, top_5_products (with match status),
        top_5_customers, revenue_trend (year over year), seasonal_patterns,
        average_order_value, match_rate_prediction.
        """
        if not raw_data:
            return {
                "date_range": None,
                "total_orders": 0,
                "total_revenue": 0.0,
                "top_products": [],
                "top_customers": [],
                "revenue_trend": [],
                "seasonal_patterns": {},
                "average_order_value": 0.0,
                "match_rate_prediction": 0.0,
            }

        date_field = column_mapping.get("date")
        customer_field = column_mapping.get("customer")
        product_field = column_mapping.get("product")
        total_field = column_mapping.get("total")
        qty_field = column_mapping.get("quantity")
        price_field = column_mapping.get("unit_price")

        # Parse dates
        dates = []
        for row in raw_data:
            if date_field and date_field in row:
                parsed = _parse_date(row[date_field])
                if parsed:
                    dates.append(parsed)

        date_range = None
        if dates:
            date_range = {
                "start": min(dates).isoformat(),
                "end": max(dates).isoformat(),
                "years_covered": (max(dates) - min(dates)).days / 365.25,
            }

        # Revenue calculation
        total_revenue = 0.0
        order_revenues = []
        for row in raw_data:
            amount = _parse_number(row.get(total_field)) if total_field else None
            if amount is None and qty_field and price_field:
                qty = _parse_number(row.get(qty_field))
                price = _parse_number(row.get(price_field))
                if qty is not None and price is not None:
                    amount = qty * price
            if amount is not None:
                total_revenue += amount
                order_revenues.append(amount)

        # Top products by frequency and revenue
        product_stats = defaultdict(lambda: {"count": 0, "revenue": 0.0})
        if product_field:
            for row in raw_data:
                product_name = str(row.get(product_field, "")).strip()
                if product_name:
                    product_stats[product_name]["count"] += 1
                    amount = _parse_number(row.get(total_field)) if total_field else 0.0
                    product_stats[product_name]["revenue"] += amount or 0.0

        top_products = sorted(
            [
                {"name": name, "order_count": stats["count"], "revenue": round(stats["revenue"], 2)}
                for name, stats in product_stats.items()
            ],
            key=lambda x: x["revenue"],
            reverse=True,
        )[:5]

        # Check match status for top products
        if top_products:
            existing_products = (
                db.query(Product)
                .filter(
                    Product.company_id == company_id,
                    Product.is_active == True,  # noqa: E712
                )
                .all()
            )
            product_names_lower = {p.name.lower() for p in existing_products}
            for tp in top_products:
                tp["likely_match"] = tp["name"].lower() in product_names_lower

        # Top customers by frequency and revenue
        customer_stats = defaultdict(lambda: {"count": 0, "revenue": 0.0})
        if customer_field:
            for row in raw_data:
                customer_name = str(row.get(customer_field, "")).strip()
                if customer_name:
                    customer_stats[customer_name]["count"] += 1
                    amount = _parse_number(row.get(total_field)) if total_field else 0.0
                    customer_stats[customer_name]["revenue"] += amount or 0.0

        top_customers = sorted(
            [
                {"name": name, "order_count": stats["count"], "revenue": round(stats["revenue"], 2)}
                for name, stats in customer_stats.items()
            ],
            key=lambda x: x["revenue"],
            reverse=True,
        )[:5]

        # Revenue trend by year
        yearly_revenue = defaultdict(float)
        for i, row in enumerate(raw_data):
            if date_field and i < len(dates):
                year = dates[i].year if i < len(dates) else None
            else:
                year = None
            if year:
                amount = _parse_number(row.get(total_field)) if total_field else 0.0
                yearly_revenue[year] += amount or 0.0

        revenue_trend = [
            {"year": year, "revenue": round(rev, 2)}
            for year, rev in sorted(yearly_revenue.items())
        ]

        # Seasonal patterns by month
        monthly_counts = defaultdict(int)
        monthly_revenue = defaultdict(float)
        for i, row in enumerate(raw_data):
            if i < len(dates):
                month = dates[i].month
                monthly_counts[month] += 1
                amount = _parse_number(row.get(total_field)) if total_field else 0.0
                monthly_revenue[month] += amount or 0.0

        seasonal_patterns = {}
        if monthly_counts:
            avg_count = sum(monthly_counts.values()) / 12
            for month in range(1, 13):
                count = monthly_counts.get(month, 0)
                seasonal_patterns[month] = {
                    "order_count": count,
                    "revenue": round(monthly_revenue.get(month, 0), 2),
                    "intensity": round(count / avg_count, 2) if avg_count > 0 else 0.0,
                }

        # Average order value
        avg_order_value = (
            round(sum(order_revenues) / len(order_revenues), 2)
            if order_revenues
            else 0.0
        )

        # Match rate prediction based on product name diversity
        unique_products = len(product_stats)
        match_rate = min(0.95, 0.5 + (0.05 * min(unique_products, 10)))

        return {
            "date_range": date_range,
            "total_orders": len(raw_data),
            "total_revenue": round(total_revenue, 2),
            "top_products": top_products,
            "top_customers": top_customers,
            "revenue_trend": revenue_trend,
            "seasonal_patterns": seasonal_patterns,
            "average_order_value": avg_order_value,
            "match_rate_prediction": round(match_rate, 2),
        }

    @staticmethod
    def extract_pricing_history(
        raw_data: list[dict],
        product_matches: dict,
        column_mapping: dict,
    ) -> dict:
        """Extract historical pricing per product.

        Returns a dict keyed by product name with price history entries.
        """
        date_field = column_mapping.get("date")
        product_field = column_mapping.get("product")
        price_field = column_mapping.get("unit_price")

        if not product_field or not price_field:
            return {"products": {}, "note": "Missing product or price column mapping"}

        pricing = defaultdict(list)

        for row in raw_data:
            product_name = str(row.get(product_field, "")).strip()
            price = _parse_number(row.get(price_field))
            if not product_name or price is None:
                continue

            date_str = row.get(date_field, "") if date_field else ""
            parsed_date = _parse_date(date_str) if date_str else None

            pricing[product_name].append({
                "price": round(price, 2),
                "date": parsed_date.isoformat() if parsed_date else None,
            })

        # Summarize per product
        product_pricing = {}
        for product_name, entries in pricing.items():
            prices = [e["price"] for e in entries]
            product_pricing[product_name] = {
                "entry_count": len(entries),
                "min_price": min(prices),
                "max_price": max(prices),
                "avg_price": round(sum(prices) / len(prices), 2),
                "current_price": entries[-1]["price"],
                "price_changes": _detect_price_changes(entries),
                "matched_product_id": product_matches.get(product_name),
            }

        return {"products": product_pricing}

    @staticmethod
    def extract_seasonal_patterns(
        raw_data: list[dict], column_mapping: dict
    ) -> dict:
        """Extract monthly order patterns for intelligence calibration.

        Returns monthly averages, peak months, and spring burial season detection.
        """
        date_field = column_mapping.get("date")
        qty_field = column_mapping.get("quantity")

        if not date_field:
            return {"patterns": {}, "note": "No date column mapped"}

        monthly_data = defaultdict(lambda: {"count": 0, "total_qty": 0})

        for row in raw_data:
            parsed_date = _parse_date(row.get(date_field, ""))
            if not parsed_date:
                continue

            month = parsed_date.month
            monthly_data[month]["count"] += 1
            if qty_field:
                qty = _parse_number(row.get(qty_field))
                if qty:
                    monthly_data[month]["total_qty"] += int(qty)

        if not monthly_data:
            return {"patterns": {}, "note": "No valid dates found"}

        # Calculate averages
        total_months_with_data = len(monthly_data)
        avg_monthly_orders = sum(m["count"] for m in monthly_data.values()) / 12

        month_names = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]

        patterns = {}
        for month in range(1, 13):
            data = monthly_data.get(month, {"count": 0, "total_qty": 0})
            intensity = round(data["count"] / avg_monthly_orders, 2) if avg_monthly_orders > 0 else 0.0
            patterns[month_names[month]] = {
                "order_count": data["count"],
                "total_quantity": data["total_qty"],
                "intensity": intensity,
                "classification": (
                    "peak" if intensity >= 1.3
                    else "above_average" if intensity >= 1.1
                    else "below_average" if intensity <= 0.7
                    else "average"
                ),
            }

        # Detect spring burial season (March-May)
        spring_months = [3, 4, 5]
        spring_intensity = sum(
            monthly_data.get(m, {"count": 0})["count"] for m in spring_months
        )
        non_spring_months = [m for m in range(1, 13) if m not in spring_months]
        non_spring_avg = sum(
            monthly_data.get(m, {"count": 0})["count"] for m in non_spring_months
        ) / 9 if non_spring_months else 0

        spring_factor = (
            round((spring_intensity / 3) / non_spring_avg, 2)
            if non_spring_avg > 0
            else 0.0
        )

        return {
            "patterns": patterns,
            "spring_burial_factor": spring_factor,
            "has_spring_peak": spring_factor > 1.2,
            "peak_months": [
                month_names[m] for m in range(1, 13)
                if monthly_data.get(m, {"count": 0})["count"] > avg_monthly_orders * 1.3
            ],
        }


def _parse_date(date_str: str) -> datetime | None:
    """Try multiple date formats."""
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%Y", "%d-%b-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _parse_number(value) -> float | None:
    """Parse a numeric value, stripping currency symbols and commas."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _detect_price_changes(entries: list[dict]) -> list[dict]:
    """Detect significant price changes in a product's history."""
    if len(entries) < 2:
        return []

    # Sort by date
    dated = [e for e in entries if e.get("date")]
    dated.sort(key=lambda x: x["date"])

    changes = []
    prev_price = None
    for entry in dated:
        if prev_price is not None and entry["price"] != prev_price:
            pct_change = round((entry["price"] - prev_price) / prev_price * 100, 1)
            if abs(pct_change) >= 2.0:  # Only track changes >= 2%
                changes.append({
                    "date": entry["date"],
                    "old_price": prev_price,
                    "new_price": entry["price"],
                    "pct_change": pct_change,
                })
        prev_price = entry["price"]

    return changes
