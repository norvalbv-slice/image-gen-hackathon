#!/bin/bash
# Test the ComfyUI Flux 2.0 FP8 Food Generator endpoint
# Now with SCENE-BASED generation for meaningful variety!
#
# Usage: 
#   RUNPOD_API_KEY=your_key ./test_fp8_endpoint.sh [scene] [num_images]
#
# Examples:
#   ./test_fp8_endpoint.sh                     # rustic_italian, 4 images
#   ./test_fp8_endpoint.sh modern_minimal      # modern_minimal, 4 images  
#   ./test_fp8_endpoint.sh premium_upscale 2   # premium_upscale, 2 images
#
# Available scenes:
#   - rustic_italian   (Traditional pizzeria, warm, inviting)
#   - modern_minimal   (Clean, Instagram-worthy, white marble)
#   - cozy_homestyle   (Checkered tablecloth, family-style)
#   - premium_upscale  (Dark slate, dramatic lighting, fine dining)
#   - street_food      (Urban, energetic, food truck vibes)
#   - garden_fresh     (Organic, farm-to-table, natural)

ENDPOINT_ID="mjiwr7uipx2nbs"

if [ -z "$RUNPOD_API_KEY" ]; then
    echo "Please set RUNPOD_API_KEY environment variable"
    echo ""
    echo "Usage: RUNPOD_API_KEY=your_key ./test_fp8_endpoint.sh [scene] [num_images]"
    echo ""
    echo "Examples:"
    echo "  ./test_fp8_endpoint.sh rustic_italian 4"
    echo "  ./test_fp8_endpoint.sh modern_minimal 2"
    echo ""
    echo "Available scenes:"
    echo "  rustic_italian, modern_minimal, cozy_homestyle,"
    echo "  premium_upscale, street_food, garden_fresh"
    exit 1
fi

# Parse arguments - scene first, num_images second
SCENE=${1:-rustic_italian}
NUM_IMAGES=${2:-4}

# Validate scene is not a number (common mistake)
if [[ "$SCENE" =~ ^[0-9]+$ ]]; then
    echo "⚠️  ERROR: First argument should be a SCENE name, not a number!"
    echo ""
    echo "Usage: ./test_fp8_endpoint.sh [scene] [num_images]"
    echo "Example: ./test_fp8_endpoint.sh rustic_italian 4"
    echo ""
    echo "Available scenes: rustic_italian, modern_minimal, cozy_homestyle,"
    echo "                  premium_upscale, street_food, garden_fresh"
    exit 1
fi

# Validate num_images is a number
if ! [[ "$NUM_IMAGES" =~ ^[0-9]+$ ]]; then
    echo "⚠️  ERROR: Second argument should be a NUMBER of images (1-4)!"
    echo ""
    echo "Usage: ./test_fp8_endpoint.sh [scene] [num_images]"
    echo "Example: ./test_fp8_endpoint.sh rustic_italian 4"
    exit 1
fi

echo "🍕 Generating ${NUM_IMAGES} pizza images with scene: ${SCENE}"
echo "   Each image will have a DIFFERENT composition/angle!"

# DEV MODE: Check for custom config URLs
DEV_MODE_JSON=""
if [ -n "$SCENES_URL" ]; then
    echo "🔧 DEV MODE: Using custom scenes from: $SCENES_URL"
    DEV_MODE_JSON="\"scenes_url\": \"${SCENES_URL}\","
fi
if [ -n "$TEMPLATES_URL" ]; then
    echo "🔧 DEV MODE: Using custom templates from: $TEMPLATES_URL"
    DEV_MODE_JSON="${DEV_MODE_JSON}\"templates_url\": \"${TEMPLATES_URL}\","
fi

echo "⚠️  First run downloads ~54GB of models - expect 5-10 min cold start"
echo ""

# Submit the job
RESPONSE=$(curl -s -X POST \
  "https://api.runpod.ai/v2/${ENDPOINT_ID}/run" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      '"${DEV_MODE_JSON}"'
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
    echo "❌ Failed to submit job"
    echo "Response: $RESPONSE"
    exit 1
fi

# Poll for completion
echo "Polling for completion..."
POLL_COUNT=0
MAX_POLLS=120  # 10 minutes max

while [ $POLL_COUNT -lt $MAX_POLLS ]; do
    RESULT=$(curl -s -X GET \
      "https://api.runpod.ai/v2/${ENDPOINT_ID}/status/${JOB_ID}" \
      -H "Authorization: Bearer ${RUNPOD_API_KEY}")
    
    STATUS=$(echo $RESULT | jq -r '.status')
    
    if [ "$STATUS" == "COMPLETED" ]; then
        echo ""
        echo "✅ Job completed!"
        
        # Extract response
        OUTPUT=$(echo $RESULT | jq -r '.output')
        NUM_GENERATED=$(echo $OUTPUT | jq -r '.num_images // 1')
        SCENE_NAME=$(echo $OUTPUT | jq -r '.scene_name // "unknown"')
        AVAILABLE=$(echo $OUTPUT | jq -r '.available_scenes | join(", ") // "N/A"')
        
        echo "   Scene: $SCENE_NAME"
        echo "   Images generated: $NUM_GENERATED"
        echo "   Available scenes: $AVAILABLE"
        echo ""
        
        # Save all images with variation info
        for i in $(seq 0 $((NUM_GENERATED - 1))); do
            # Try new format first (.images[i].image_base64)
            IMAGE_B64=$(echo $OUTPUT | jq -r ".images[$i].image_base64 // empty")
            SEED=$(echo $OUTPUT | jq -r ".images[$i].seed // empty")
            ANGLE=$(echo $OUTPUT | jq -r ".images[$i].variation.angle // \"unknown\"")
            
            # Fallback to old format (.image_base64 at root)
            if [ -z "$IMAGE_B64" ] && [ "$i" -eq 0 ]; then
                IMAGE_B64=$(echo $OUTPUT | jq -r ".image_base64 // empty")
                SEED=$(echo $OUTPUT | jq -r ".seed // \"unknown\"")
                ANGLE="default"
            fi
            
            if [ -n "$IMAGE_B64" ]; then
                # Clean filename from angle description
                ANGLE_CLEAN=$(echo "$ANGLE" | tr ' ' '_' | tr -cd '[:alnum:]_-')
                FILENAME="${SCENE}_${i}_${ANGLE_CLEAN}_seed${SEED}.png"
                echo $IMAGE_B64 | base64 -d > $FILENAME
                echo "   [$((i+1))] Saved: $FILENAME"
                echo "       Angle: $ANGLE"
            fi
        done
        
        echo ""
        echo "🎨 Each image has a different angle/composition!"
        echo "   Shops can pick their favorite and maintain that style across their menu."
        
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
