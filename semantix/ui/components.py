"""NiceGUI reusable components."""
from nicegui import ui
from semantix.store.schema import ItemResponse


def status_chip(status: str) -> ui.element:
    """Create a status chip."""
    colors = {
        "voting": "orange",
        "approved": "green",
        "rejected": "red",
        "queued": "blue",
    }
    color = colors.get(status, "grey")
    return ui.badge(status.upper(), color=color)


def vote_controls(item_id: str, on_vote: callable) -> ui.element:
    """Create vote control buttons."""
    with ui.row().classes("gap-2"):
        ui.button("👍 Positive", on_click=lambda: on_vote(item_id, "positive", 1)).classes("bg-green-500")
        ui.button("👎 Negative", on_click=lambda: on_vote(item_id, "negative", 1)).classes("bg-red-500")
        ui.button("⭐ Quality +", on_click=lambda: on_vote(item_id, None, 1, quality=1)).classes("bg-yellow-500")
        ui.button("⭐ Quality -", on_click=lambda: on_vote(item_id, None, 1, quality=-1)).classes("bg-yellow-300")


def item_detail_drawer(item: ItemResponse, on_vote: callable) -> ui.element:
    """Create item detail drawer."""
    with ui.drawer(value=True, side="right").classes("w-2/3 p-4") as drawer:
        with ui.column().classes("gap-4 w-full"):
            ui.label(f"Item: {item.item.id[:16]}...").classes("text-2xl font-bold")
            
            # Status
            status_chip(item.status)
            
            # Metadata
            with ui.card():
                ui.label("Metadata").classes("text-lg font-semibold")
                ui.label(f"Source: {item.item.source}")
                ui.label(f"Created: {item.item.created_at}")
                ui.label(f"MIME: {item.item.meta.mime}")
                ui.label(f"Bytes: {item.item.meta.bytes:,}")
            
            # Votes
            with ui.card():
                ui.label("Votes").classes("text-lg font-semibold")
                ui.label(f"Quality: {item.quality}")
                for label, count in item.votes.items():
                    if label.startswith("label:"):
                        label_name = label.replace("label:", "")
                        ui.label(f"{label_name}: {count}")
            
            # Vote controls
            vote_controls(item.item.id, on_vote)
            
            # Text content
            with ui.card():
                ui.label("Content").classes("text-lg font-semibold")
                ui.textarea(value=item.item.text, readonly=True).classes("w-full").style("min-height: 300px")
    
    return drawer

