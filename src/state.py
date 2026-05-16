"""KV state management for incremental scraping (olx-cars #17).

Functions:
  load_snapshot(kv_store, state_key) -> dict[str, dict]
  compute_diff(item_dict, snapshot, run_ts) -> (changeType, firstSeenAt, lastSeenAt, updated_entry)
  _fields_changed(item_dict, prior_entry) -> bool
  compute_missing(snapshot, seen_offer_ids, emit_missing, run_ts, was_truncated) -> list[dict]
  save_snapshot(kv_store, state_key, snapshot) -> None

Pure state module — no Scrapy dependencies. Testable in isolation.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Fields tracked for change detection (price, currency, condition, mileageKm, title)
TRACKED_FIELDS = ('price', 'currency', 'condition', 'mileageKm', 'title')

# Number of consecutive MISSING runs before an entry is purged from the snapshot
MISSING_PURGE_THRESHOLD = 3


async def load_snapshot(kv_store, state_key: str) -> dict[str, dict]:
    """Load the snapshot dict from Apify KV store.

    Returns an empty dict if the key is absent, invalid, or not a dict.
    Treats any error as a fresh baseline (logs WARNING).
    """
    try:
        value = await kv_store.get_value(state_key)
    except Exception as exc:
        logger.warning(
            "State key %r: error reading from KV store (%s: %s) — treating as fresh baseline.",
            state_key, type(exc).__name__, exc,
        )
        return {}

    if value is None:
        logger.warning(
            "State key %r not found in KV store — treating as fresh baseline.",
            state_key,
        )
        return {}

    if not isinstance(value, dict):
        logger.warning(
            "State key %r: value is %r (expected dict) — treating as fresh baseline.",
            state_key, type(value).__name__,
        )
        return {}

    return value


def _fields_changed(item_dict: dict, prior_entry: dict) -> bool:
    """Return True if any of the 5 tracked fields differ between item and snapshot entry.

    Both sides may be None (missing field).
    None == None is treated as unchanged; value != None is changed.
    """
    for field in TRACKED_FIELDS:
        item_val = item_dict.get(field)
        prior_val = prior_entry.get(field)
        if item_val != prior_val:
            return True
    return False


def compute_diff(
    item_dict: dict,
    snapshot: dict,
    run_ts: str,
) -> tuple[str, str, str, dict]:
    """Diff one item against the snapshot and return change metadata.

    Args:
        item_dict: The scraped item as a plain Python dict.
        snapshot: The full snapshot dict (keys = str(offerId)).
        run_ts: ISO 8601 UTC string for this run (used as lastSeenAt).

    Returns:
        (changeType, firstSeenAt, lastSeenAt, new_snapshot_entry)
        where new_snapshot_entry should be written to snapshot[offer_id_str].
    """
    offer_id_str = str(item_dict['offerId'])

    if offer_id_str not in snapshot:
        change_type = 'NEW'
        first_seen_at = run_ts
    else:
        prior = snapshot[offer_id_str]
        missing_count = prior.get('_missingCount', 0)
        if missing_count > 0:
            # Was missing in a prior run — now back in results
            change_type = 'REAPPEARED'
            first_seen_at = prior['firstSeenAt']  # preserve original firstSeenAt
        elif _fields_changed(item_dict, prior):
            change_type = 'UPDATED'
            first_seen_at = prior['firstSeenAt']
        else:
            change_type = 'UNCHANGED'
            first_seen_at = prior['firstSeenAt']

    last_seen_at = run_ts

    # Build the new snapshot entry (compact: strip None values, always include timestamps)
    new_entry: dict = {
        'price': item_dict.get('price'),
        'currency': item_dict.get('currency'),
        'condition': item_dict.get('condition'),
        'mileageKm': item_dict.get('mileageKm'),
        'title': item_dict.get('title'),
        'firstSeenAt': first_seen_at,
        'lastSeenAt': last_seen_at,
        # _missingCount is omitted (reset to 0 / absent on any present run)
    }
    # Strip None values for compact storage (timestamps always present so safe)
    new_entry = {k: v for k, v in new_entry.items() if v is not None}
    # Timestamps are always present — re-ensure they survive the None-strip
    new_entry['firstSeenAt'] = first_seen_at
    new_entry['lastSeenAt'] = last_seen_at

    return change_type, first_seen_at, last_seen_at, new_entry


def compute_missing(
    snapshot: dict,
    seen_ids: set,
    emit_missing: bool,
    run_ts: str,
    was_truncated: bool,
) -> list[dict]:
    """Compute MISSING items and mutate snapshot for purging.

    Args:
        snapshot: The updated in-memory snapshot (mutated in-place).
        seen_ids: set of str(offerId) values seen in the current run.
        emit_missing: Whether to include MISSING items in the returned list.
        run_ts: ISO 8601 UTC string for this run (not applied to MISSING lastSeenAt).
        was_truncated: If True, MISSING detection is suppressed to avoid false positives.

    Returns:
        List of MISSING item dicts (empty if emit_missing=False or was_truncated=True).
    """
    if was_truncated:
        logger.warning(
            'maxItems cap reached — MISSING detection suppressed for this run '
            'to avoid false positives.'
        )
        return []

    missing_items: list[dict] = []
    # Collect keys to modify/delete after iteration (can't modify dict during iteration)
    to_purge: list[str] = []
    to_increment: list[str] = []

    for offer_id_str, entry in snapshot.items():
        if offer_id_str in seen_ids:
            continue  # listing was present in this run

        # Listing absent from this run
        current_count = entry.get('_missingCount', 0)
        new_count = current_count + 1

        if new_count >= MISSING_PURGE_THRESHOLD:
            # Purge this entry after 3 consecutive absences
            if emit_missing:
                # Emit the MISSING item before purging
                missing_item = {k: v for k, v in entry.items() if k != '_missingCount'}
                missing_item['offerId'] = offer_id_str
                missing_item['changeType'] = 'MISSING'
                missing_items.append(missing_item)
            to_purge.append(offer_id_str)
        else:
            if emit_missing:
                # Emit the MISSING item (count < threshold, so listing still in snapshot)
                missing_item = {k: v for k, v in entry.items() if k != '_missingCount'}
                missing_item['offerId'] = offer_id_str
                missing_item['changeType'] = 'MISSING'
                missing_items.append(missing_item)
            to_increment.append((offer_id_str, new_count))

    # Apply mutations
    for offer_id_str in to_purge:
        del snapshot[offer_id_str]

    for offer_id_str, new_count in to_increment:
        snapshot[offer_id_str]['_missingCount'] = new_count

    if to_purge:
        logger.info('Incremental mode: purged %d entries (absent >= %d runs).', len(to_purge), MISSING_PURGE_THRESHOLD)

    return missing_items


async def save_snapshot(kv_store, state_key: str, snapshot: dict) -> None:
    """Save the updated snapshot dict to Apify KV store.

    The Apify KV client serialises the dict as JSON automatically.
    """
    await kv_store.set_value(state_key, snapshot)
    logger.info("Snapshot saved: %d entries to key %r.", len(snapshot), state_key)
