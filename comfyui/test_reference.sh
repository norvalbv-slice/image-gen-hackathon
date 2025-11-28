#!/bin/bash
# Test reference image scene extraction
# This script takes an existing food photo and uses GPT-4V to extract the scene,
# then generates new images matching that style.
#
# Usage:
#   RUNPOD_API_KEY=your_key OPENAI_API_KEY=your_key ./test_reference.sh path/to/reference.jpg
#
# The reference image will be analyzed by GPT-4V to extract:
# - Background/surface style
# - Lighting characteristics
# - Mood/atmosphere
# - Props and composition
#
# Then Flux 2.0 generates new images matching that extracted scene.

ENDPOINT_ID="hbvg2b5ucr59mx"

if [ -z "$RUNPOD_API_KEY" ]; then
    echo "Please set RUNPOD_API_KEY environment variable"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "Please set OPENAI_API_KEY environment variable (for GPT-5.1 scene analysis)"
    exit 1
fi

if [ -z "$1" ]; then
    echo "Usage: ./test_reference.sh <path_to_reference_image> [num_images]"
    echo ""
    echo "Example:"
    echo "  ./test_reference.sh my_pizza_photo.jpg 4"
    echo ""
    echo "This will:"
    echo "  1. Analyze my_pizza_photo.jpg with GPT-4V"
    echo "  2. Extract scene characteristics (lighting, background, mood)"
    echo "  3. Generate 4 new images matching that style"
    exit 1
fi

REFERENCE_IMAGE="$1"
NUM_IMAGES=${2:-4}

# Check if file exists
if [ ! -f "$REFERENCE_IMAGE" ]; then
    echo "Error: File not found: $REFERENCE_IMAGE"
    exit 1
fi

# Convert image to base64
echo "📸 Converting reference image to base64..."
REFERENCE_BASE64=$(base64 -i "$REFERENCE_IMAGE" | tr -d '\n')

echo "🔍 Submitting job with reference image extraction..."
echo "   Reference: $REFERENCE_IMAGE"
echo "   Generating: $NUM_IMAGES images"
echo "   GPT-4V will analyze the reference and extract scene characteristics"
echo ""

# Submit the job
RESPONSE=$(curl -s -X POST \
  "https://api.runpod.ai/v2/${ENDPOINT_ID}/run" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "item_name": "pepperoni pizza",
      "item_description": "pepperoni slices, mozzarella cheese, marinara sauce, fresh basil",
      "reference_image": "'"${REFERENCE_BASE64}"'",
      "extract_scene": true,
      "openai_api_key": "'"${OPENAI_API_KEY}"'",
      "save_scene_as": "my_shop_style",
      "num_images": '"${NUM_IMAGES}"'
    }
  }')

JOB_ID=$(echo $RESPONSE | jq -r '.id')
STATUS=$(echo $RESPONSE | jq -r '.status')

echo "Job ID: $JOB_ID"
echo "Initial status: $STATUS"
echo ""

if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
    echo "❌ Failed to submit job"
    echo "Response: $RESPONSE"
    exit 1
fi

echo "Polling for completion (GPT-5.1 analysis + image generation)..."
POLL_COUNT=0
MAX_POLLS=180  # 15 minutes max (scene extraction + generation)

while [ $POLL_COUNT -lt $MAX_POLLS ]; do
    RESULT=$(curl -s -X GET \
      "https://api.runpod.ai/v2/${ENDPOINT_ID}/status/${JOB_ID}" \
      -H "Authorization: Bearer ${RUNPOD_API_KEY}")
    
    STATUS=$(echo $RESULT | jq -r '.status')
    
    if [ "$STATUS" == "COMPLETED" ]; then
        echo ""
        echo "✅ Job completed!"
        
        # Save to temp file FIRST to avoid any variable expansion of 4MB data
        TEMP_FILE=$(mktemp)
        curl -s "https://api.runpod.ai/v2/${ENDPOINT_ID}/status/${JOB_ID}" \
          -H "Authorization: Bearer ${RUNPOD_API_KEY}" > "$TEMP_FILE"
        
        # Extract metadata from file (fast - jq reads file directly)
        MODE=$(jq -r '.output.mode // "unknown"' "$TEMP_FILE")
        SCENE_NAME=$(jq -r '.output.scene_name // "Custom Style"' "$TEMP_FILE")
        NUM_GENERATED=$(jq -r '.output.num_images // 1' "$TEMP_FILE")
        
        echo ""
        echo "📋 Extracted Scene: $SCENE_NAME"
        echo "   Mode: $MODE"
        echo "   Images generated: $NUM_GENERATED"
        
        # Show extracted scene details
        echo ""
        echo "🎨 Scene Characteristics:"
        jq -r '.output.extracted_scene | "   Background: \(.background // "N/A")\n   Lighting: \(.lighting // "N/A")\n   Mood: \(.mood // "N/A")\n   Props: \(.props // "N/A")"' "$TEMP_FILE"
        
        # Save generated images
        echo ""
        echo "💾 Saving generated images..."
        
        for i in $(seq 0 $((NUM_GENERATED - 1))); do
            SEED=$(jq -r ".output.images[$i].seed // \"unknown\"" "$TEMP_FILE")
            VARIATION=$(jq -r ".output.images[$i].variation.angle // \"variation_$i\"" "$TEMP_FILE" | tr ' ' '_')
            
            FILENAME="ref_extracted_${i}_${VARIATION}_seed${SEED}.png"
            jq -r ".output.images[$i].image_base64 // empty" "$TEMP_FILE" | base64 -d > "$FILENAME" 2>/dev/null
            
            if [ -s "$FILENAME" ]; then
                echo "   [$((i+1))] Saved: $FILENAME"
            fi
        done
        
        # Show save_scene_as if returned
        SCENE_ID=$(jq -r '.output.scene_id // "N/A"' "$TEMP_FILE")
        if [ "$SCENE_ID" != "N/A" ] && [ "$SCENE_ID" != "null" ]; then
            echo ""
            echo "💡 Scene ID for reuse: $SCENE_ID"
            echo "   The Owners Portal can save this scene config for future generations"
        fi
        
        rm -f "$TEMP_FILE"
        exit 0
    elif [ "$STATUS" == "FAILED" ]; then
        echo ""
        echo "❌ Job failed!"
        echo $RESULT | jq '.output'
        exit 1
    else
        echo -n "."
        sleep 5
        POLL_COUNT=$((POLL_COUNT + 1))
    fi
done

echo ""
echo "⏰ Timeout waiting for job completion"
exit 1

