#!/bin/bash
# Test the ComfyUI Flux 2.0 FP8 Pizza Generator endpoint
# Usage: RUNPOD_API_KEY=your_key ./test_fp8_endpoint.sh

ENDPOINT_ID="mjiwr7uipx2nbs"  # A100-only endpoint (faster!)

if [ -z "$RUNPOD_API_KEY" ]; then
    echo "Please set RUNPOD_API_KEY environment variable"
    echo "Usage: RUNPOD_API_KEY=your_key ./test_fp8_endpoint.sh"
    exit 1
fi

echo "🍕 Submitting pizza generation job to Flux 2.0 FP8 endpoint..."
echo "⚠️  First run downloads ~54GB of models - expect 5-10 min cold start"
echo ""

# Submit the job
RESPONSE=$(curl -s -X POST \
  "https://api.runpod.ai/v2/${ENDPOINT_ID}/run" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "item_name": "pepperoni pizza",
      "item_description": "pepperoni slices, mozzarella cheese, marinara sauce"
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

# Poll for completion
echo "Polling for completion (this may take 5-10 minutes on first run)..."
while true; do
    RESULT=$(curl -s \
      "https://api.runpod.ai/v2/${ENDPOINT_ID}/status/${JOB_ID}" \
      -H "Authorization: Bearer ${RUNPOD_API_KEY}")
    
    STATUS=$(echo $RESULT | jq -r '.status')
    
    case $STATUS in
        "COMPLETED")
            echo ""
            echo "✅ Job completed!"
            
            # Check for error in output
            ERROR=$(echo $RESULT | jq -r '.output.error // empty')
            if [ -n "$ERROR" ]; then
                echo "❌ Generation failed: $ERROR"
                exit 1
            fi
            
            # Save the image
            IMAGE_B64=$(echo $RESULT | jq -r '.output.image_base64')
            if [ "$IMAGE_B64" != "null" ] && [ -n "$IMAGE_B64" ]; then
                echo "$IMAGE_B64" | base64 -d > pizza_fp8_output.png
                echo "🖼️  Image saved to pizza_fp8_output.png"
                
                SEED=$(echo $RESULT | jq -r '.output.seed')
                echo "🎲 Seed used: $SEED"
                
                # Open the image on macOS
                if [ "$(uname)" == "Darwin" ]; then
                    open pizza_fp8_output.png
                fi
            else
                echo "⚠️  No image in response"
                echo "Full output: $(echo $RESULT | jq '.output')"
            fi
            exit 0
            ;;
        "FAILED")
            echo ""
            echo "❌ Job failed!"
            echo "Error: $(echo $RESULT | jq -r '.error // .output.error // "Unknown error"')"
            exit 1
            ;;
        "IN_QUEUE"|"IN_PROGRESS")
            echo -n "."
            sleep 5
            ;;
        *)
            echo ""
            echo "Unknown status: $STATUS"
            echo "Full response: $RESULT"
            sleep 5
            ;;
    esac
done

