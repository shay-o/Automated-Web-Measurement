"""
GTM Container Generator - Produces a Google Tag Manager container JSON
that can be imported directly into GTM. Implements the tracking plan
as tags, triggers, and variables.
"""

import json
import time
import logging
from typing import Any

logger = logging.getLogger(__name__)

# GTM container export format version
GTM_EXPORT_VERSION = 2
GTM_TAG_MANAGER_VERSION = "2"


def generate_gtm_container(analyses, ga4_measurement_id: str = "G-XXXXXXXXXX", output_path: str = "gtm_container.json"):
    """Generate a complete GTM container JSON from page analyses."""

    container = {
        "exportFormatVersion": GTM_EXPORT_VERSION,
        "exportTime": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "containerVersion": {
            "tag": [],
            "trigger": [],
            "variable": [],
            "folder": [],
            "builtInVariable": _built_in_variables(),
        },
    }

    # Create organizational folders
    folders = _create_folders()
    container["containerVersion"]["folder"] = folders
    folder_map = {f["name"]: f["folderId"] for f in folders}

    # Create variables
    variables = _create_variables(analyses, folder_map)
    container["containerVersion"]["variable"] = variables

    # Create triggers and tags from analyses
    triggers = []
    tags = []
    trigger_id_counter = 1
    tag_id_counter = 1

    # Collect unique events
    event_registry = {}
    for a in analyses:
        for e in a.recommended_events:
            name = e["event_name"]
            if name not in event_registry:
                event_registry[name] = e
                event_registry[name]["_page_types"] = {a.page_type}
            else:
                event_registry[name]["_page_types"].add(a.page_type)

    # Page View trigger (built-in, fires on all pages)
    page_view_trigger = {
        "triggerId": str(trigger_id_counter),
        "name": "All Pages - Page View",
        "type": "PAGEVIEW",
        "filter": [],
        "parentFolderId": folder_map["Core Triggers"],
    }
    triggers.append(page_view_trigger)
    trigger_id_counter += 1

    # GA4 Configuration Tag
    config_tag = {
        "tagId": str(tag_id_counter),
        "name": "GA4 - Configuration",
        "type": "gaawc",
        "parameter": [
            {"type": "TEMPLATE", "key": "measurementId", "value": ga4_measurement_id},
            {"type": "BOOLEAN", "key": "sendPageView", "value": "true"},
            {"type": "LIST", "key": "fieldsToSet", "list": [
                {"type": "MAP", "map": [
                    {"type": "TEMPLATE", "key": "name", "value": "content_group"},
                    {"type": "TEMPLATE", "key": "value", "value": "{{DLV - content_group}}"},
                ]},
            ]},
        ],
        "firingTriggerId": [page_view_trigger["triggerId"]],
        "parentFolderId": folder_map["GA4 Tags"],
        "tagFiringOption": "ONCE_PER_EVENT",
    }
    tags.append(config_tag)
    tag_id_counter += 1

    # Create event-specific triggers and tags
    for event_name, event_data in event_registry.items():
        if event_name == "page_view":
            continue  # Handled by config tag

        # Create Custom Event trigger
        trigger = {
            "triggerId": str(trigger_id_counter),
            "name": f"CE - {event_name}",
            "type": "CUSTOM_EVENT",
            "customEventFilter": [
                {
                    "type": "EQUALS",
                    "parameter": [
                        {"type": "TEMPLATE", "key": "arg0", "value": "{{_event}}"},
                        {"type": "TEMPLATE", "key": "arg1", "value": event_name},
                    ],
                }
            ],
            "parentFolderId": folder_map["Event Triggers"],
        }
        triggers.append(trigger)
        trigger_id_counter += 1

        # Determine if this is an e-commerce event
        params = event_data.get("parameters", {})
        is_ecommerce = "items" in params or event_name in (
            "view_item", "view_item_list", "select_item", "add_to_cart",
            "remove_from_cart", "view_cart", "begin_checkout", "purchase",
            "add_shipping_info", "add_payment_info",
            "view_promotion", "select_promotion",
        )

        # Create GA4 Event Tag
        tag_params = [
            {"type": "BOOLEAN", "key": "sendEcommerceData", "value": "true" if is_ecommerce else "false"},
            {"type": "TEMPLATE", "key": "eventName", "value": event_name},
            {"type": "TAG_REFERENCE", "key": "measurementId", "value": "GA4 - Configuration"},
        ]

        # Add non-ecommerce event parameters
        if not is_ecommerce:
            event_params_list = []
            for param_name, param_desc in params.items():
                event_params_list.append({
                    "type": "MAP",
                    "map": [
                        {"type": "TEMPLATE", "key": "name", "value": param_name},
                        {"type": "TEMPLATE", "key": "value", "value": f"{{{{DLV - {param_name}}}}}"},
                    ],
                })
            if event_params_list:
                tag_params.append({
                    "type": "LIST",
                    "key": "eventParameters",
                    "list": event_params_list,
                })
        else:
            # For ecommerce events, GTM reads from dataLayer ecommerce object automatically
            # but we still add non-item parameters
            event_params_list = []
            for param_name, param_desc in params.items():
                if param_name == "items":
                    continue
                event_params_list.append({
                    "type": "MAP",
                    "map": [
                        {"type": "TEMPLATE", "key": "name", "value": param_name},
                        {"type": "TEMPLATE", "key": "value", "value": f"{{{{DLV - ecommerce.{param_name}}}}}"},
                    ],
                })
            if event_params_list:
                tag_params.append({
                    "type": "LIST",
                    "key": "eventParameters",
                    "list": event_params_list,
                })

        tag = {
            "tagId": str(tag_id_counter),
            "name": f"GA4 Event - {event_name}",
            "type": "gaawe",
            "parameter": tag_params,
            "firingTriggerId": [trigger["triggerId"]],
            "parentFolderId": folder_map["GA4 Tags"],
            "tagFiringOption": "ONCE_PER_EVENT",
        }
        tags.append(tag)
        tag_id_counter += 1

    container["containerVersion"]["tag"] = tags
    container["containerVersion"]["trigger"] = triggers

    with open(output_path, "w") as f:
        json.dump(container, f, indent=2)

    logger.info(f"GTM container saved to {output_path}")
    return container


def _built_in_variables():
    return [
        {"type": "PAGE_URL", "name": "Page URL"},
        {"type": "PAGE_HOSTNAME", "name": "Page Hostname"},
        {"type": "PAGE_PATH", "name": "Page Path"},
        {"type": "REFERRER", "name": "Referrer"},
        {"type": "EVENT", "name": "Event"},
        {"type": "CLICK_ELEMENT", "name": "Click Element"},
        {"type": "CLICK_CLASSES", "name": "Click Classes"},
        {"type": "CLICK_ID", "name": "Click ID"},
        {"type": "CLICK_URL", "name": "Click URL"},
        {"type": "CLICK_TEXT", "name": "Click Text"},
        {"type": "FORM_ELEMENT", "name": "Form Element"},
        {"type": "FORM_ID", "name": "Form ID"},
        {"type": "SCROLL_DEPTH_THRESHOLD", "name": "Scroll Depth Threshold"},
        {"type": "SCROLL_DEPTH_DIRECTION", "name": "Scroll Depth Direction"},
    ]


def _create_folders():
    return [
        {"folderId": "1", "name": "GA4 Tags"},
        {"folderId": "2", "name": "Core Triggers"},
        {"folderId": "3", "name": "Event Triggers"},
        {"folderId": "4", "name": "Data Layer Variables"},
        {"folderId": "5", "name": "Utility Variables"},
    ]


def _create_variables(analyses, folder_map):
    """Create GTM variables for data layer values referenced by tags."""
    variables = []
    var_id = 1

    # Collect all unique parameter names
    all_params = set()
    ecommerce_params = set()
    for a in analyses:
        for e in a.recommended_events:
            params = e.get("parameters", {})
            is_ecom = "items" in params
            for param_name in params:
                if param_name == "items":
                    continue
                if is_ecom:
                    ecommerce_params.add(param_name)
                else:
                    all_params.add(param_name)

    # Standard data layer variables
    for param in sorted(all_params):
        variables.append({
            "variableId": str(var_id),
            "name": f"DLV - {param}",
            "type": "v",
            "parameter": [
                {"type": "INTEGER", "key": "dataLayerVersion", "value": "2"},
                {"type": "TEMPLATE", "key": "name", "value": param},
            ],
            "parentFolderId": folder_map["Data Layer Variables"],
        })
        var_id += 1

    # Ecommerce data layer variables
    for param in sorted(ecommerce_params):
        variables.append({
            "variableId": str(var_id),
            "name": f"DLV - ecommerce.{param}",
            "type": "v",
            "parameter": [
                {"type": "INTEGER", "key": "dataLayerVersion", "value": "2"},
                {"type": "TEMPLATE", "key": "name", "value": f"ecommerce.{param}"},
            ],
            "parentFolderId": folder_map["Data Layer Variables"],
        })
        var_id += 1

    # Content group variable
    variables.append({
        "variableId": str(var_id),
        "name": "DLV - content_group",
        "type": "v",
        "parameter": [
            {"type": "INTEGER", "key": "dataLayerVersion", "value": "2"},
            {"type": "TEMPLATE", "key": "name", "value": "content_group"},
        ],
        "parentFolderId": folder_map["Data Layer Variables"],
    })

    return variables
