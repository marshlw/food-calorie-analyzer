import React, { useEffect, useRef, useState } from 'react'
import { ArrowRight, RefreshCw } from 'lucide-react'
import { AppHeader } from '../components/Brand'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorAlert } from '../components/ErrorAlert'
import { useApi } from '../hooks/useApi'
import { advisorApi } from '../api/advisor'
import { AdvisorResponse, AdvisorAskResponse, AdvisorTip } from '../types'

// Цвет точки-маркера рекомендации по тегу (из дизайна 3c)
const TAG_DOT: Record<string, string> = {
  protein: 'bg-protein dark:bg-protein-dark',
  water: 'bg-water',
  calories: 'bg-primary-500 dark:bg-primary-400',
  carbs: 'bg-carbs dark:bg-carbs-dark',
  training: 'bg-primary-500 dark:bg-primary-400',
  general: 'bg-carbs dark:bg-carbs-dark',
}

const TipCard: React.FC<{ tip: AdvisorTip }> = ({ tip }) => (
  <div className="card-tile p-4 flex gap-3">
    <span
      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 mt-1.5 ${
        TAG_DOT[tip.tag] ?? TAG_DOT.general
      }`}
    />
    <div>
      <div className="text-sm font-semibold">{tip.title}</div>
      <div className="text-xs text-secondary mt-0.5 leading-relaxed">{tip.text}</div>
    </div>
  </div>
)

export const Advisor: React.FC = () => {
  const { data, isLoading, error, execute: load } = useApi<AdvisorResponse>()

  const [question, setQuestion] = useState('')
  const answerRef = useRef<HTMLDivElement>(null)
  const askApi = useApi<AdvisorAskResponse>({
    onSuccess: () => {
      setQuestion('')
      setTimeout(() => answerRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    },
  })

  const loadAdvice = () => {
    load(() => advisorApi.getAdvice()).catch(() => {
      // Ошибка уже показана через error
    })
  }

  useEffect(() => {
    loadAdvice()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault()
    const q = question.trim()
    if (q.length < 3 || askApi.isLoading) return
    try {
      await askApi.execute(() => advisorApi.ask(q))
    } catch {
      // Ошибка уже показана через askApi.error
    }
  }

  return (
    <div className="max-w-md mx-auto px-5 pt-6 pb-32">
      <AppHeader />

      <div className="mb-5">
        <h1 className="font-display font-bold text-2xl tracking-tight">Советы для вас</h1>
        <p className="text-[13px] text-secondary mt-1">
          На основе питания, тренировок и вашей цели
        </p>
      </div>

      {error && (
        <div className="mb-4">
          <ErrorAlert message={error} onClose={() => {}} />
          <button onClick={loadAdvice} className="btn-secondary w-full mt-3">
            Повторить
          </button>
        </div>
      )}

      {isLoading && !data && <LoadingSpinner message="✦ Советчик изучает ваши данные..." />}

      {data && (
        <>
          {/* Совет дня — тёмная градиентная карточка */}
          <div className="rounded-card p-[22px] text-[#eef1f7] bg-gradient-to-br from-ink to-[#1a2942] mb-4">
            <div className="flex items-center justify-between mb-3">
              <span className="chip bg-primary-400/15 text-primary-400">✦ Совет дня</span>
              <button
                onClick={loadAdvice}
                disabled={isLoading}
                aria-label="Обновить советы"
                className="p-1.5 rounded-full text-[#8b96ad] hover:text-white hover:bg-white/10 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              </button>
            </div>
            <div className="font-display font-bold text-lg mb-2">{data.headline_title}</div>
            <div className="text-sm leading-relaxed">{data.headline_text}</div>
            {data.generated_by === 'rules' && (
              <div className="text-[11px] text-[#8b96ad] mt-3">
                AI сейчас недоступен — советы построены по вашим данным автоматически.
              </div>
            )}
          </div>

          {/* Питание */}
          {data.nutrition.length > 0 && (
            <>
              <div className="section-title mb-3">Питание</div>
              <div className="flex flex-col gap-2.5 mb-6">
                {data.nutrition.map((tip, i) => (
                  <TipCard key={`n-${i}`} tip={tip} />
                ))}
              </div>
            </>
          )}

          {/* Тренировки */}
          {data.training.length > 0 && (
            <>
              <div className="section-title mb-3">Тренировки</div>
              <div className="flex flex-col gap-2.5 mb-6">
                {data.training.map((tip, i) => (
                  <TipCard key={`t-${i}`} tip={tip} />
                ))}
              </div>
            </>
          )}
        </>
      )}

      {/* Ответ на вопрос */}
      {askApi.error && (
        <div className="mb-3">
          <ErrorAlert message={askApi.error} onClose={() => {}} />
        </div>
      )}
      {askApi.data && (
        <div ref={answerRef} className="card p-4 mb-3">
          <span className="chip-ai mb-2">✦ Ответ советчика</span>
          <div className="text-sm leading-relaxed whitespace-pre-line">{askApi.data.answer}</div>
        </div>
      )}
      {askApi.isLoading && <LoadingSpinner message="✦ Думаю над ответом..." />}

      {/* Вопрос AI — pill-поле из дизайна */}
      <form
        onSubmit={handleAsk}
        className="bg-white dark:bg-card-dark border border-line dark:border-line-dark rounded-full p-1.5 pl-[18px] flex items-center gap-2.5"
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Спросить: «что съесть перед тренировкой?»"
          maxLength={500}
          disabled={askApi.isLoading}
          className="flex-1 min-w-0 bg-transparent border-none p-0 text-sm placeholder-faint dark:placeholder-faint-dark focus:outline-none focus:ring-0"
        />
        <button
          type="submit"
          disabled={askApi.isLoading || question.trim().length < 3}
          aria-label="Отправить вопрос"
          className="w-10 h-10 rounded-full bg-primary-500 hover:bg-primary-700 text-white flex items-center justify-center flex-shrink-0 transition-colors disabled:opacity-50"
        >
          <ArrowRight className="h-[18px] w-[18px]" />
        </button>
      </form>
    </div>
  )
}
