"""VSCS XCIC queue-loader custom node package for ComfyUI."""

from .xcic_queue_loader import XCICQueueJobLoader

NODE_CLASS_MAPPINGS = {"XCICQueueJobLoader": XCICQueueJobLoader}
NODE_DISPLAY_NAME_MAPPINGS = {"XCICQueueJobLoader": "XCIC Queue Job Loader"}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
