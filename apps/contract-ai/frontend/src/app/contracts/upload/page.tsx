'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import FileUpload from '@/components/forms/FileUpload'
import Badge from '@/components/ui/Badge'

export default function ContractUploadPage() {
  const router = useRouter()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)

  const [formData, setFormData] = useState({
    contractType: '',
    partyA: '',
    partyB: '',
    description: ''
  })

  const contractTypes = [
    'Договор подряда',
    'Договор поставки',
    'Договор аренды',
    'Трудовой договор',
    'Договор оказания услуг',
    'Договор купли-продажи',
    'Агентский договор',
    'Лицензионный договор',
    'Другое'
  ]

  const handleFileSelect = (file: File) => {
    setSelectedFile(file)
  }

  const handleUpload = async () => {
    if (!selectedFile || !formData.contractType) {
      alert('Пожалуйста, загрузите файл и выберите тип договора')
      return
    }

    setUploading(true)
    setUploadProgress(0)

    // Simulate upload progress
    const interval = setInterval(() => {
      setUploadProgress(prev => {
        if (prev >= 90) {
          clearInterval(interval)
          return 90
        }
        return prev + 10
      })
    }, 200)

    try {
      const formDataToSend = new FormData()
      formDataToSend.append('file', selectedFile)
      formDataToSend.append('contractType', formData.contractType)
      formDataToSend.append('partyA', formData.partyA)
      formDataToSend.append('partyB', formData.partyB)
      formDataToSend.append('description', formData.description)

      const response = await fetch('/api/contracts/upload', {
        method: 'POST',
        body: formDataToSend
      })

      if (!response.ok) throw new Error('Upload failed')

      const result = await response.json()

      setUploadProgress(100)
      clearInterval(interval)

      // Redirect to contract details page
      setTimeout(() => {
        router.push(`/contracts/${result.contractId}`)
      }, 500)

    } catch (error) {
      clearInterval(interval)
      console.error('Upload error:', error)
      alert('Ошибка загрузки файла. Пожалуйста, попробуйте снова.')
      setUploading(false)
      setUploadProgress(0)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
      <nav className="bg-white/80 backdrop-blur-lg shadow-lg border-b border-white/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-3 cursor-pointer"
              onClick={() => router.push('/dashboard')}
            >
              <div className="w-10 h-10 bg-gradient-primary rounded-xl shadow-lg flex items-center justify-center">
                <span className="text-2xl">📄</span>
              </div>
              <span className="text-xl font-bold gradient-text">Contract AI</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
            >
              <Button variant="outline" size="sm" onClick={() => router.push('/contracts')}>
                ← К списку договоров
              </Button>
            </motion.div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-5xl font-bold gradient-text mb-4">
            Загрузка договора
          </h1>
          <p className="text-xl text-gray-600">
            Загрузите договор для автоматического анализа и обработки
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Upload Form */}
          <div className="lg:col-span-2">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <Card>
                <h2 className="text-2xl font-bold text-gray-900 mb-6">
                  Файл договора
                </h2>

                <FileUpload
                  onFileSelect={handleFileSelect}
                  disabled={uploading}
                />

                {selectedFile && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-4 p-4 bg-success-50 border border-success-200 rounded-xl flex items-center justify-between"
                  >
                    <div className="flex items-center">
                      <svg className="h-8 w-8 text-success-500 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <div>
                        <p className="font-semibold text-success-900">{selectedFile.name}</p>
                        <p className="text-sm text-success-700">
                          {(selectedFile.size / 1024 / 1024).toFixed(2)} МБ
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => setSelectedFile(null)}
                      disabled={uploading}
                      className="p-2 hover:bg-success-100 rounded-lg transition-colors"
                    >
                      <svg className="h-5 w-5 text-success-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </motion.div>
                )}
              </Card>
            </motion.div>

            {/* Contract Details Form */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="mt-8"
            >
              <Card>
                <h2 className="text-2xl font-bold text-gray-900 mb-6">
                  Информация о договоре
                </h2>

                <div className="space-y-6">
                  {/* Contract Type */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Тип договора <span className="text-danger-500">*</span>
                    </label>
                    <select
                      value={formData.contractType}
                      onChange={(e) => setFormData({ ...formData, contractType: e.target.value })}
                      disabled={uploading}
                      className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
                    >
                      <option value="">Выберите тип договора</option>
                      {contractTypes.map(type => (
                        <option key={type} value={type}>{type}</option>
                      ))}
                    </select>
                  </div>

                  {/* Party A */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Сторона А (Заказчик/Покупатель)
                    </label>
                    <input
                      type="text"
                      value={formData.partyA}
                      onChange={(e) => setFormData({ ...formData, partyA: e.target.value })}
                      disabled={uploading}
                      placeholder="ООО Компания А"
                      className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
                    />
                  </div>

                  {/* Party B */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Сторона Б (Исполнитель/Продавец)
                    </label>
                    <input
                      type="text"
                      value={formData.partyB}
                      onChange={(e) => setFormData({ ...formData, partyB: e.target.value })}
                      disabled={uploading}
                      placeholder="ИП Иванов И.И."
                      className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
                    />
                  </div>

                  {/* Description */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Описание (необязательно)
                    </label>
                    <textarea
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      disabled={uploading}
                      placeholder="Краткое описание договора..."
                      rows={3}
                      className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors resize-none"
                    />
                  </div>
                </div>

                {/* Upload Progress */}
                {uploading && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-6"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold text-gray-700">Загрузка файла...</span>
                      <span className="text-sm font-bold text-primary-600">{uploadProgress}%</span>
                    </div>
                    <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${uploadProgress}%` }}
                        className="h-full bg-gradient-primary"
                        transition={{ duration: 0.3 }}
                      />
                    </div>
                  </motion.div>
                )}

                {/* Upload Button */}
                <div className="mt-8">
                  <Button
                    variant="primary"
                    className="w-full"
                    onClick={handleUpload}
                    loading={uploading}
                    disabled={!selectedFile || !formData.contractType}
                  >
                    {uploading ? 'Загрузка...' : 'Загрузить и проанализировать'}
                  </Button>
                </div>
              </Card>
            </motion.div>
          </div>

          {/* Info Sidebar */}
          <div className="lg:col-span-1">
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
            >
              <Card className="sticky top-8">
                <h3 className="text-lg font-bold text-gray-900 mb-4">
                  Что произойдёт после загрузки?
                </h3>

                <div className="space-y-4">
                  <div className="flex items-start">
                    <div className="flex-shrink-0 w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center mr-3">
                      <span className="text-white font-bold text-sm">1</span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">Парсинг документа</p>
                      <p className="text-xs text-gray-600">Извлечение текста и структуры</p>
                    </div>
                  </div>

                  <div className="flex items-start">
                    <div className="flex-shrink-0 w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center mr-3">
                      <span className="text-white font-bold text-sm">2</span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">AI анализ</p>
                      <p className="text-xs text-gray-600">Выявление рисков и недочетов</p>
                    </div>
                  </div>

                  <div className="flex items-start">
                    <div className="flex-shrink-0 w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center mr-3">
                      <span className="text-white font-bold text-sm">3</span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">Рекомендации</p>
                      <p className="text-xs text-gray-600">Предложения по улучшению</p>
                    </div>
                  </div>

                  <div className="flex items-start">
                    <div className="flex-shrink-0 w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center mr-3">
                      <span className="text-white font-bold text-sm">4</span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">Отчёт</p>
                      <p className="text-xs text-gray-600">Детальный отчёт с выводами</p>
                    </div>
                  </div>
                </div>

                <div className="mt-6 pt-6 border-t border-gray-200">
                  <h4 className="text-sm font-bold text-gray-900 mb-3">
                    Поддерживаемые форматы:
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="info" size="sm">PDF</Badge>
                    <Badge variant="info" size="sm">DOCX</Badge>
                  </div>
                </div>

                <div className="mt-4">
                  <h4 className="text-sm font-bold text-gray-900 mb-3">
                    Макс. размер файла:
                  </h4>
                  <Badge variant="default" size="sm">10 МБ</Badge>
                </div>
              </Card>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  )
}
