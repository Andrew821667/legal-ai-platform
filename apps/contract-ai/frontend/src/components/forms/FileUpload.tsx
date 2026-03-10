'use client'

import { useDropzone } from 'react-dropzone'
import { motion } from 'framer-motion'
import { useState } from 'react'

interface FileUploadProps {
  onFileSelect: (file: File) => void
  accept?: Record<string, string[]>
  maxSize?: number
  disabled?: boolean
}

export default function FileUpload({
  onFileSelect,
  accept = {
    'application/pdf': ['.pdf'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx']
  },
  maxSize = 10 * 1024 * 1024, // 10MB
  disabled = false
}: FileUploadProps) {
  const [error, setError] = useState<string | null>(null)

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    accept,
    maxSize,
    disabled,
    multiple: false,
    onDrop: (acceptedFiles, rejectedFiles) => {
      setError(null)

      if (rejectedFiles.length > 0) {
        const rejection = rejectedFiles[0]
        if (rejection.errors[0]?.code === 'file-too-large') {
          setError('Файл слишком большой. Максимум 10 МБ')
        } else if (rejection.errors[0]?.code === 'file-invalid-type') {
          setError('Неподдерживаемый формат файла. Используйте PDF или DOCX')
        } else {
          setError('Ошибка загрузки файла')
        }
        return
      }

      if (acceptedFiles.length > 0) {
        onFileSelect(acceptedFiles[0])
      }
    }
  })

  const rootProps = getRootProps({
    className: `
      border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer
      transition-all duration-300
      ${isDragActive && !isDragReject ? 'border-primary-500 bg-primary-50 scale-105' : ''}
      ${isDragReject ? 'border-danger-500 bg-danger-50' : ''}
      ${!isDragActive && !isDragReject ? 'border-gray-300 hover:border-primary-400 hover:bg-gray-50' : ''}
      ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
    `
  })

  return (
    <div>
      <div {...rootProps}>
        <input {...getInputProps()} />

        <motion.div
          whileHover={{ scale: disabled ? 1 : 1.01 }}
          animate={{
            y: isDragActive ? -10 : 0,
            scale: isDragActive ? 1.1 : 1
          }}
          transition={{ type: "spring", stiffness: 300 }}
        >
          {isDragActive ? (
            <>
              <div className="text-6xl mb-4">📄</div>
              <p className="text-xl font-semibold text-primary-600 mb-2">
                Отпустите файл здесь
              </p>
            </>
          ) : (
            <>
              <div className="flex justify-center mb-4">
                <div className="w-20 h-20 bg-gradient-primary rounded-2xl shadow-lg flex items-center justify-center">
                  <svg className="h-10 w-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                </div>
              </div>

              <p className="text-lg font-semibold text-gray-700 mb-2">
                Перетащите файл сюда или кликните для выбора
              </p>
              <p className="text-sm text-gray-500">
                Поддерживаются форматы: PDF, DOCX • Максимум 10 МБ
              </p>
            </>
          )}
        </motion.div>
      </div>

      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 p-4 bg-danger-50 border border-danger-200 rounded-xl flex items-start"
        >
          <svg className="h-5 w-5 text-danger-500 mr-2 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-danger-700 font-medium">{error}</p>
        </motion.div>
      )}
    </div>
  )
}
