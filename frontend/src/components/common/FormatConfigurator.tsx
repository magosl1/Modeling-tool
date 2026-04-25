import { useFormattingStore, NumericsUnit } from '../../store/formattingStore'
import { useState, useRef, useEffect } from 'react'

export default function FormatConfigurator() {
  const { decimals, unit, separatorStyle, setDecimals, setUnit, setSeparatorStyle } = useFormattingStore()
  const [isOpen, setIsOpen] = useState(false)
  const popupRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (popupRef.current && !popupRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [popupRef]);

  return (
    <div className="relative" ref={popupRef}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="text-xs font-medium px-3 py-1.5 border border-gray-300 rounded-md bg-white hover:bg-gray-50 flex items-center gap-2 text-gray-700 shadow-sm"
      >
        ⚙️ Formatting
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-xl border border-gray-200 z-50 overflow-hidden">
          <div className="p-3 bg-gray-50 border-b text-xs font-semibold text-gray-700">
            Number Formatting
          </div>
          <div className="p-4 space-y-4">
            
            {/* Decimals */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-gray-700">Decimals</label>
              <div className="flex bg-gray-100 rounded-md p-0.5">
                {[0, 1, 2].map(d => (
                  <button
                    key={d}
                    onClick={() => setDecimals(d)}
                    className={`flex-1 text-xs py-1 rounded-sm transition-colors ${decimals === d ? 'bg-white shadow text-primary-700 font-medium' : 'text-gray-500 hover:text-gray-700'}`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>

            {/* Units */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-gray-700">Units</label>
              <div className="grid grid-cols-2 gap-1">
                {(['exact', 'thousands', 'millions', 'billions'] as NumericsUnit[]).map(u => (
                  <button
                    key={u}
                    onClick={() => setUnit(u)}
                    className={`text-xs py-1.5 px-2 rounded border transition-colors ${unit === u ? 'border-primary-500 bg-primary-50 text-primary-700 font-medium' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}
                  >
                    {u.charAt(0).toUpperCase() + u.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Separators */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-gray-700">Separators</label>
              <div className="flex bg-gray-100 rounded-md p-0.5">
                <button
                  onClick={() => setSeparatorStyle('us')}
                  className={`flex-1 text-xs py-1.5 rounded-sm transition-colors ${separatorStyle === 'us' ? 'bg-white shadow text-primary-700 font-medium' : 'text-gray-500 hover:text-gray-700'}`}
                >
                  1,000.00
                </button>
                <button
                  onClick={() => setSeparatorStyle('eu')}
                  className={`flex-1 text-xs py-1.5 rounded-sm transition-colors ${separatorStyle === 'eu' ? 'bg-white shadow text-primary-700 font-medium' : 'text-gray-500 hover:text-gray-700'}`}
                >
                  1.000,00
                </button>
              </div>
            </div>

          </div>
        </div>
      )}
    </div>
  )
}
