"""NiceGUI pages and UI."""
import asyncio
import json
import logging
from typing import Dict, Optional

import httpx
from nicegui import app, ui

from semantix.config import settings
from semantix.ui.components import item_detail_drawer, status_chip, vote_controls

logger = logging.getLogger(__name__)

# WebSocket connection
ws_connection: Optional[ui.websocket] = None

# State
metrics_state: Dict = {}
items_state: list[Dict] = []
selected_item: Optional[Dict] = None


async def fetch_metrics() -> Dict:
    """Fetch metrics from API."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8080/backend/api/metrics")
        return response.json()


async def fetch_items(status: Optional[str] = None, limit: int = 100) -> list[Dict]:
    """Fetch items from API."""
    async with httpx.AsyncClient() as client:
        params = {"limit": limit}
        if status:
            params["status"] = status
        response = await client.get("http://localhost:8080/backend/api/items", params=params)
        return response.json().get("items", [])


async def cast_vote_api(item_id: str, label: Optional[str] = None, delta: int = 1, quality: Optional[int] = None) -> Dict:
    """Cast vote via API."""
    async with httpx.AsyncClient() as client:
        payload = {"voter": "ui_user", "delta": delta}
        if label:
            payload["label"] = label
        if quality is not None:
            payload["quality"] = quality
        response = await client.post(f"http://localhost:8080/backend/api/vote/{item_id}", json=payload)
        return response.json()


async def get_item_api(item_id: str) -> Dict:
    """Get item detail from API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8080/backend/api/item/{item_id}")
        return response.json()


def build_ui() -> None:
    """Build NiceGUI pages."""
    
    @ui.page("/")
    async def dashboard():
        """Dashboard page."""
        ui.page_title("Semantix - Dashboard")
        
        with ui.header().classes("bg-blue-500 text-white p-4"):
            ui.label("Semantix Dashboard").classes("text-2xl font-bold")
        
        with ui.column().classes("p-4 gap-4 w-full"):
            # Metrics cards
            with ui.row().classes("gap-4 w-full"):
                with ui.card().classes("p-4"):
                    ui.label("Total Items").classes("text-lg")
                    total_label = ui.label("0").classes("text-3xl font-bold")
                
                with ui.card().classes("p-4"):
                    ui.label("Pending").classes("text-lg")
                    pending_label = ui.label("0").classes("text-3xl font-bold text-orange-500")
                
                with ui.card().classes("p-4"):
                    ui.label("Approved").classes("text-lg")
                    approved_label = ui.label("0").classes("text-3xl font-bold text-green-500")
                
                with ui.card().classes("p-4"):
                    ui.label("Rejected").classes("text-lg")
                    rejected_label = ui.label("0").classes("text-3xl font-bold text-red-500")
            
            # Refresh button
            async def refresh_metrics():
                metrics = await fetch_metrics()
                total_label.text = str(metrics.get("total_items", 0))
                pending_label.text = str(metrics.get("pending_items", 0))
                approved_label.text = str(metrics.get("approved_items", 0))
                rejected_label.text = str(metrics.get("rejected_items", 0))
            
            ui.button("Refresh", on_click=refresh_metrics)
            
            # Initial load
            await refresh_metrics()
            
            # Auto-refresh every 5 seconds
            ui.timer(5.0, refresh_metrics)
    
    @ui.page("/items")
    async def inbox():
        """Inbox page - list of pending items."""
        ui.page_title("Semantix - Inbox")
        
        with ui.header().classes("bg-blue-500 text-white p-4"):
            ui.label("Inbox - Pending Items").classes("text-2xl font-bold")
        
        with ui.column().classes("p-4 gap-4 w-full"):
            # Filters
            with ui.row().classes("gap-2"):
                status_filter = ui.select(
                    ["pending", "approved", "rejected"],
                    value="pending",
                    label="Status",
                )
                
                ui.button("Filter", on_click=apply_filter_with_data)
            
            # Items table
            columns = [
                {"name": "id", "label": "ID", "field": "id"},
                {"name": "source", "label": "Source", "field": "source"},
                {"name": "status", "label": "Status", "field": "status"},
                {"name": "quality", "label": "Quality", "field": "quality"},
                {"name": "preview", "label": "Preview", "field": "preview"},
            ]
            
            # Store full item data
            items_data = {}
            
            table = ui.table(
                columns=columns,
                rows=[],
                row_key="id",
            ).classes("w-full")
            
            async def on_row_click(e):
                row_id = e.args[1]["id"]
                # Find full item ID from stored data
                for item_id, item in items_data.items():
                    if item_id.startswith(row_id.replace("...", "")):
                        item_detail = await get_item_api(item_id)
                        show_item_detail(item_detail)
                        break
            
            table.on("rowClick", on_row_click)
            
            async def apply_filter_with_data():
                items = await fetch_items(status=status_filter.value)
                items_data.clear()
                table_rows = []
                for item in items:
                    items_data[item["id"]] = item
                    table_rows.append({
                        "id": item["id"][:16] + "...",
                        "source": item["source"],
                        "status": item["status"],
                        "quality": item["quality"],
                        "preview": item["text_preview"],
                    })
                table.rows = table_rows
                table.update()
            
            # Initial load
            await apply_filter_with_data()
            
            # Auto-refresh every 10 seconds
            ui.timer(10.0, apply_filter_with_data)
    
    @ui.page("/item/{item_id}")
    async def item_detail(item_id: str):
        """Item detail page."""
        ui.page_title(f"Semantix - Item {item_id[:16]}")
        
        with ui.header().classes("bg-blue-500 text-white p-4"):
            ui.label(f"Item: {item_id[:16]}...").classes("text-2xl font-bold")
        
        with ui.column().classes("p-4 gap-4 w-full"):
            item_data = await get_item_api(item_id)
            show_item_detail(item_data)
    
    @ui.page("/train")
    async def training():
        """Training page."""
        ui.page_title("Semantix - Training")
        
        with ui.header().classes("bg-blue-500 text-white p-4"):
            ui.label("Training").classes("text-2xl font-bold")
        
        with ui.column().classes("p-4 gap-4 w-full"):
            # Training form
            with ui.card().classes("p-4"):
                ui.label("Training Configuration").classes("text-lg font-semibold")
                
                filter_label_input = ui.input("Filter Label (optional)", placeholder="e.g., positive")
                min_quality_input = ui.number("Min Quality", value=1, min=0, max=10)
                target_size_input = ui.number("Target Size (optional)", value=None, min=1)
                
                progress_bar = ui.linear_progress(value=0).classes("w-full")
                status_label = ui.label("Ready").classes("text-lg")
                
                async def start_training():
                    status_label.text = "Starting..."
                    progress_bar.value = 0.1
                    
                    async with httpx.AsyncClient() as client:
                        payload = {
                            "filter_label": filter_label_input.value or None,
                            "min_quality": int(min_quality_input.value),
                            "target_size": int(target_size_input.value) if target_size_input.value else None,
                        }
                        response = await client.post("http://localhost:8080/backend/api/train/kick", json=payload)
                        result = response.json()
                        
                        status_label.text = f"Job queued: {result.get('job_id')}"
                        progress_bar.value = 0.5
                
                ui.button("Start Training", on_click=start_training).classes("bg-green-500")
    
    @ui.page("/settings")
    async def settings_page():
        """Settings page."""
        ui.page_title("Semantix - Settings")
        
        with ui.header().classes("bg-blue-500 text-white p-4"):
            ui.label("Settings").classes("text-2xl font-bold")
        
        with ui.column().classes("p-4 gap-4 w-full"):
            with ui.card().classes("p-4"):
                ui.label("Voting Thresholds").classes("text-lg font-semibold")
                ui.label(f"Vote Threshold: {settings.VOTE_THRESHOLD}")
                ui.label(f"Quality Minimum: {settings.QUALITY_MIN}")
            
            with ui.card().classes("p-4"):
                ui.label("Auto-labeling").classes("text-lg font-semibold")
                ui.label(f"Enabled: {settings.AUTO_LABEL_ENABLED}")
                ui.label(f"Provider: {settings.LLM_PROVIDER}")
                if settings.LLM_PROVIDER == "ollama":
                    ui.label(f"Ollama URL: {settings.OLLAMA_BASE_URL}")
                    ui.label(f"Model: {settings.OLLAMA_MODEL}")


def show_item_detail(item_data: Dict) -> None:
    """Show item detail in drawer."""
    from semantix.store.schema import ItemResponse
    
    item = ItemResponse(**item_data)
    
    async def on_vote(item_id: str, label: Optional[str] = None, delta: int = 1, quality: Optional[int] = None):
        result = await cast_vote_api(item_id, label, delta, quality)
        ui.notify(f"Vote cast: {result.get('status')}")
        # Refresh item detail
        updated = await get_item_api(item_id)
        show_item_detail(updated)
    
    item_detail_drawer(item, on_vote)

