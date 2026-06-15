import { useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react'
import { TransformWrapper, TransformComponent, useControls } from 'react-zoom-pan-pinch'
import type { BoundingBox, DocumentResult } from '../../types/ticket'
import { DOC_TYPE_FIELDS, FIELD_LABELS } from '../../types/ticket'

interface FieldOverlay {
  fieldKey: string
  bbox: BoundingBox
  index: number
  confidence: number
}

interface Props {
  imageB64: string
  filename: string
  result?: DocumentResult
  activeField?: string | null
  onFieldBadgeClick?: (fieldKey: string) => void
}

export interface DocumentViewerHandle {
  zoomToField: (fieldKey: string) => void
}

// Controls toolbar rendered inside TransformWrapper context
function ZoomControls({ rotation, onRotate }: { rotation: number; onRotate: (r: number) => void }) {
  const { zoomIn, zoomOut, resetTransform } = useControls()
  return (
    <div className="flex items-center gap-1 bg-white/90 backdrop-blur border border-gray-200 rounded-lg px-2 py-1 shadow-sm">
      <button
        onClick={() => onRotate(rotation - 90)}
        className="p-1.5 hover:bg-gray-100 rounded text-gray-600 text-sm"
        title="Rotate left"
      >↺</button>
      <button
        onClick={() => onRotate(rotation + 90)}
        className="p-1.5 hover:bg-gray-100 rounded text-gray-600 text-sm"
        title="Rotate right"
      >↻</button>
      <div className="w-px h-4 bg-gray-200 mx-1" />
      <button
        onClick={() => zoomOut()}
        className="p-1.5 hover:bg-gray-100 rounded text-gray-600 font-bold text-sm w-7"
        title="Zoom out"
      >−</button>
      <button
        onClick={() => zoomIn()}
        className="p-1.5 hover:bg-gray-100 rounded text-gray-600 font-bold text-sm w-7"
        title="Zoom in"
      >+</button>
      <button
        onClick={() => resetTransform()}
        className="p-1.5 hover:bg-gray-100 rounded text-gray-500 text-xs"
        title="Reset zoom"
      >⤢</button>
    </div>
  )
}

function confidenceDotColor(score: number): string {
  if (score >= 0.85) return 'bg-green-500'
  if (score >= 0.60) return 'bg-yellow-400'
  return 'bg-red-500'
}

const DocumentViewer = forwardRef<DocumentViewerHandle, Props>(
  ({ imageB64, filename, result, activeField, onFieldBadgeClick }, ref) => {
    const [rotation, setRotation] = useState(0)
    const [highlight, setHighlight] = useState<string | null>(null)
    const transformRef = useRef<any>(null)
    const imgRef = useRef<HTMLImageElement>(null)

    const isJpeg = imageB64?.startsWith('/9j/')
    const mime = isJpeg ? 'image/jpeg' : 'image/png'

    // Build overlay list from result fields that have bboxes
    const overlays: FieldOverlay[] = []
    if (result) {
      const fileType = result.file_type || 'Ticket'
      const fieldKeys = DOC_TYPE_FIELDS[fileType] || DOC_TYPE_FIELDS['Ticket']
      fieldKeys.forEach((key, idx) => {
        const fv = (result as any)[key]
        if (fv?.bbox && fv.value) {
          overlays.push({
            fieldKey: key as string,
            bbox: fv.bbox,
            index: idx + 1,
            confidence: fv.confidence_score ?? 0,
          })
        }
      })
    }

    // Zoom to a specific field's bbox
    const zoomToField = useCallback((fieldKey: string) => {
      const overlay = overlays.find(o => o.fieldKey === fieldKey)
      if (!overlay || !transformRef.current || !imgRef.current) return

      const imgEl = imgRef.current
      const imgW = imgEl.clientWidth
      const imgH = imgEl.clientHeight

      const { x, y, w, h } = overlay.bbox
      const centerX = (x + w / 2) * imgW
      const centerY = (y + h / 2) * imgH

      const scale = 3
      transformRef.current.setTransform(
        -centerX * scale + imgW / 2,
        -centerY * scale + imgH / 2,
        scale,
        400,
      )
      setHighlight(fieldKey)
      setTimeout(() => setHighlight(null), 2000)
    }, [overlays])

    useImperativeHandle(ref, () => ({ zoomToField }), [zoomToField])

    if (!imageB64) return (
      <div className="flex items-center justify-center h-48 bg-gray-100 rounded-xl text-gray-400 text-sm">
        No preview available
      </div>
    )

    return (
      <div className="rounded-xl overflow-hidden border border-gray-200 bg-gray-50 flex flex-col">
        {/* Header */}
        <div className="bg-gray-50 px-3 py-2 text-xs text-gray-500 font-medium border-b border-gray-200 truncate">
          {filename}
        </div>

        {/* Viewer */}
        <TransformWrapper
          ref={transformRef}
          initialScale={1}
          minScale={0.5}
          maxScale={8}
          wheel={{ step: 0.1 }}
          doubleClick={{ disabled: false }}
        >
          {/* Toolbar — rendered inside TransformWrapper so useControls works */}
          {({ zoomIn: _zi, zoomOut: _zo }) => (
            <>
              <div className="absolute top-2 left-2 z-20">
                <ZoomControls rotation={rotation} onRotate={setRotation} />
              </div>

              <TransformComponent
                wrapperStyle={{ width: '100%', maxHeight: '620px', overflow: 'hidden', position: 'relative' }}
                contentStyle={{ width: '100%' }}
              >
                {/* Document image */}
                <div
                  className="relative"
                  style={{ transform: `rotate(${rotation}deg)`, transformOrigin: 'center center' }}
                >
                  <img
                    ref={imgRef}
                    src={`data:${mime};base64,${imageB64}`}
                    alt={filename}
                    className="w-full object-contain select-none"
                    draggable={false}
                  />

                  {/* Field overlays */}
                  {overlays.map((ov) => {
                    const isActive = activeField === ov.fieldKey
                    const isHighlighted = highlight === ov.fieldKey
                    return (
                      <div key={ov.fieldKey}>
                        {/* Highlight box */}
                        {isHighlighted && (
                          <div
                            className="absolute border-2 border-yellow-400 bg-yellow-100/30 rounded pointer-events-none transition-opacity duration-500"
                            style={{
                              left: `${ov.bbox.x * 100}%`,
                              top: `${ov.bbox.y * 100}%`,
                              width: `${ov.bbox.w * 100}%`,
                              height: `${ov.bbox.h * 100}%`,
                            }}
                          />
                        )}
                        {/* Active field highlight */}
                        {isActive && !isHighlighted && (
                          <div
                            className="absolute border-2 border-blue-500 bg-blue-100/20 rounded pointer-events-none"
                            style={{
                              left: `${ov.bbox.x * 100}%`,
                              top: `${ov.bbox.y * 100}%`,
                              width: `${ov.bbox.w * 100}%`,
                              height: `${ov.bbox.h * 100}%`,
                            }}
                          />
                        )}
                        {/* Numbered badge */}
                        <button
                          onClick={() => onFieldBadgeClick?.(ov.fieldKey)}
                          title={`${FIELD_LABELS[ov.fieldKey] || ov.fieldKey}`}
                          className={`absolute flex items-center justify-center w-5 h-5 rounded-full text-white text-[10px] font-bold shadow cursor-pointer border border-white/80 hover:scale-125 transition-transform z-10 ${confidenceDotColor(ov.confidence)}`}
                          style={{
                            left: `calc(${ov.bbox.x * 100}% - 10px)`,
                            top: `calc(${ov.bbox.y * 100}% - 10px)`,
                          }}
                        >
                          {ov.index}
                        </button>
                      </div>
                    )
                  })}
                </div>
              </TransformComponent>
            </>
          )}
        </TransformWrapper>

        {/* Legend */}
        {overlays.length > 0 && (
          <div className="px-3 py-2 border-t border-gray-200 bg-white flex flex-wrap gap-1.5 text-[10px] text-gray-500">
            {overlays.map(ov => (
              <button
                key={ov.fieldKey}
                onClick={() => onFieldBadgeClick?.(ov.fieldKey)}
                className={`flex items-center gap-1 px-1.5 py-0.5 rounded-full border ${activeField === ov.fieldKey ? 'border-blue-400 bg-blue-50 text-blue-700' : 'border-gray-200 hover:bg-gray-50'}`}
              >
                <span className={`w-3 h-3 rounded-full ${confidenceDotColor(ov.confidence)}`} />
                <span>{ov.index}. {FIELD_LABELS[ov.fieldKey] || ov.fieldKey}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }
)

DocumentViewer.displayName = 'DocumentViewer'
export default DocumentViewer
