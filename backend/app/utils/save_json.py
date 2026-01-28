import json
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------
# Helper function to save JSON
# ---------------------------------------------------------
def save_analysis_to_json(response_data: dict, output_dir: str = "."):
    """
    Save the analysis response to a JSON file in the specified directory.
    
    Args:
        response_data: Dictionary containing the analysis results
        output_dir: Directory where to save the file (default: current directory/root)
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    original_filename = response_data.get('filename', 'unknown')
    # Remove file extension and sanitize
    base_name = Path(original_filename).stem
    json_filename = f"analysis_{base_name}_{timestamp}.json"
    
    # Full path to save
    json_path = output_path / json_filename
    
    # Add metadata
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "analysis": response_data
    }
    
    # Save to JSON file
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"Analysis saved to: {json_path}")
    return str(json_path)
