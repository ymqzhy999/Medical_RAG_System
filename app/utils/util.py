import logging
import colorlog
import json
from sentence_transformers import CrossEncoder


def setup_logger():
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s[%(asctime)s] %(message)s',
        datefmt='%H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    ))
    logger = logging.getLogger("MedicalRAG")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


logger = setup_logger()


def log_step(step_name, input_data, output_data, cost_time=None):
    separator = "=" * 50
    log_msg = f"\n{separator}\nSTEP: {step_name}\n{separator}\n"

    if isinstance(input_data, (dict, list)):
        log_msg += f"[Input]:\n{json.dumps(input_data, ensure_ascii=False, indent=2)}\n"
    else:
        log_msg += f"[Input]: {str(input_data).strip()}\n"

    log_msg += "-" * 30 + "\n"

    if isinstance(output_data, (dict, list)):
        log_msg += f"[Output]:\n{json.dumps(output_data, ensure_ascii=False, indent=2)}\n"
    else:
        log_msg += f"[Output]: {str(output_data).strip()}\n"

    if cost_time:
        log_msg += f"Time: {cost_time:.4f}s\n"

    logger.info(log_msg)



