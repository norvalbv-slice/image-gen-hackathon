#!/bin/bash
# Test Qwen-Image-2512 endpoint
# Usage: RUNPOD_API_KEY=your_key ./test_qwen_endpoint.sh [scene] [num_images]
#
# Examples:
#   ./test_qwen_endpoint.sh rustic_italian 4
#   ./test_qwen_endpoint.sh modern_minimal 2

# IMPORTANT: Update this endpoint ID after creating the RunPod endpoint
ENDPOINT_ID="${QWEN_ENDPOINT_ID:-s4fdug7h6af60k}"

if [ -z "$RUNPOD_API_KEY" ]; then
    echo "Please set RUNPOD_API_KEY environment variable"
    exit 1
fi

SCENE=${1:-rustic_italian}
NUM_IMAGES=${2:-2}

echo "Testing Qwen-Image-2512 endpoint..."
echo "  Endpoint: $ENDPOINT_ID"
echo "  Scene: $SCENE"
echo "  Num images: $NUM_IMAGES"
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
      "scene": "'"${SCENE}"'",
      "num_images": '"${NUM_IMAGES}"'
    }
  }')

JOB_ID=$(echo $RESPONSE | jq -r '.id')
STATUS=$(echo $RESPONSE | jq -r '.status')

echo "Job ID: $JOB_ID"
echo "Initial status: $STATUS"
echo ""

if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
    echo "Failed to submit job"
    echo "Response: $RESPONSE"
    exit 1
fi

echo "Polling for completion (first run downloads ~27GB of models)..."
POLL_COUNT=0
MAX_POLLS=360  # 30 minutes max for first cold start

while [ $POLL_COUNT -lt $MAX_POLLS ]; do
    RESULT=$(curl -s -X GET \
      "https://api.runpod.ai/v2/${ENDPOINT_ID}/status/${JOB_ID}" \
      -H "Authorization: Bearer ${RUNPOD_API_KEY}")

    STATUS=$(echo $RESULT | jq -r '.status')

    if [ "$STATUS" == "COMPLETED" ]; then
        echo ""
        echo "Job completed!"

        # Save to temp file
        TEMP_FILE=$(mktemp)
        curl -s "https://api.runpod.ai/v2/${ENDPOINT_ID}/status/${JOB_ID}" \
          -H "Authorization: Bearer ${RUNPOD_API_KEY}" > "$TEMP_FILE"

        # Extract metadata
        MODEL=$(jq -r '.output.model // "unknown"' "$TEMP_FILE")
        SCENE_NAME=$(jq -r '.output.scene_name // "Unknown"' "$TEMP_FILE")
        NUM_GENERATED=$(jq -r '.output.num_images // 1' "$TEMP_FILE")

        echo ""
        echo "Model: $MODEL"
        echo "Scene: $SCENE_NAME"
        echo "Images generated: $NUM_GENERATED"

        # Save generated images
        echo ""
        echo "Saving generated images..."

        for i in $(seq 0 $((NUM_GENERATED - 1))); do
            SEED=$(jq -r ".output.images[$i].seed // \"unknown\"" "$TEMP_FILE")
            VARIATION=$(jq -r ".output.images[$i].variation.angle // \"variation_$i\"" "$TEMP_FILE" | tr ' ' '_')

            FILENAME="qwen_${SCENE}_${i}_${VARIATION}_seed${SEED}.png"
            jq -r ".output.images[$i].image_base64 // empty" "$TEMP_FILE" | base64 -d > "$FILENAME" 2>/dev/null

            if [ -s "$FILENAME" ]; then
                echo "   [$((i+1))] Saved: $FILENAME"
            fi
        done

        rm -f "$TEMP_FILE"
        exit 0
    elif [ "$STATUS" == "FAILED" ]; then
        echo ""
        echo "Job failed!"
        echo $RESULT | jq '.output'
        exit 1
    else
        echo -n "."
        sleep 5
        POLL_COUNT=$((POLL_COUNT + 1))
    fi
done

echo ""
echo "Timeout waiting for job completion"
exit 1
