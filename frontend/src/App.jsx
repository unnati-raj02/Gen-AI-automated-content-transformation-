import React, { useState } from 'react';
import './App.css';

const OUTPUT_TYPES = [
  { id: 'Executive Summary', label: 'Executive Summary', icon: '\u{1F4CB}' },
  { id: 'Advisory', label: 'Advisory', icon: '\u{26A0}\u{FE0F}' },
  { id: 'LinkedIn Post', label: 'LinkedIn Post', icon: '\u{1F680}' },
];

const TONE_OPTIONS = ['Professional', 'Urgent', 'Casual', 'Inspiring', 'Informative', 'Persuasive'];
const DETAIL_LEVELS = ['Brief', 'Moderate', 'Detailed'];
const LANGUAGES = ['English', 'Hindi', 'Spanish', 'French', 'German'];

function App() {
  const [sourceContent, setSourceContent] = useState('');
  const [outputType, setOutputType] = useState('Executive Summary');
  const [targetAudience, setTargetAudience] = useState('C-suite Executives');
  const [tone, setTone] = useState('Professional');
  const [language, setLanguage] = useState('English');
  const [detailLevel, setDetailLevel] = useState('Brief');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleTransform = async (e) => {
    e.preventDefault();

    if (!sourceContent.trim()) {
      setError('Please provide source content to transform.');
      return;
    }

    setLoading(true);
    setError(null);

    const payload = {
      source_content: sourceContent.trim(),
      output_type: outputType,
      target_audience: targetAudience.trim() || null,
      tone: tone || null,
      language: language || 'English',
      detail_level: detailLevel || null,
    };

    try {
      const response = await fetch('http://127.0.0.1:8000/transform', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Server error (${response.status})`);
      }

      setResult(data);
    } catch (err) {
      console.error('Transformation error:', err);
      setError(err.message || 'Failed to connect to backend server. Make sure FastAPI is running on port 8000.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (result && result.transformed_content) {
      navigator.clipboard.writeText(result.transformed_content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="badge">
          <span className="badge-dot"></span>
          AI Content Transformer · SIH MVP
        </div>
        <h1>Transform Source Into Impact</h1>
        <p>Convert raw information into structured Executive Summaries, Advisories, and LinkedIn Posts using Gemini.</p>
      </header>

      {/* Main Grid */}
      <main className="main-layout">
        {/* Left Column: Form Controls */}
        <section className="card">
          <h2 className="card-title">1. Source & Configuration</h2>

          <form onSubmit={handleTransform}>
            {/* Source Content */}
            <div className="form-group">
              <label htmlFor="source-content" className="form-label">
                <span>Source Content *</span>
                <span className="char-counter">{sourceContent.length} characters</span>
              </label>
              <textarea
                id="source-content"
                className="form-textarea"
                placeholder="Paste or write your raw notes, operational updates, draft announcements, or meeting minutes here..."
                value={sourceContent}
                onChange={(e) => setSourceContent(e.target.value)}
                disabled={loading}
                required
              />
            </div>

            {/* Output Type Selector */}
            <div className="form-group">
              <label className="form-label">Output Type *</label>
              <div className="output-type-grid">
                {OUTPUT_TYPES.map((type) => (
                  <button
                    key={type.id}
                    type="button"
                    className={`output-type-btn ${outputType === type.id ? 'active' : ''}`}
                    onClick={() => setOutputType(type.id)}
                    disabled={loading}
                  >
                    <div>{type.icon} {type.label}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Configuration Controls Grid */}
            <div className="form-group">
              <label className="form-label">Audience & Style Tuning</label>
              <div className="config-grid">
                {/* Target Audience */}
                <div>
                  <label htmlFor="target-audience" className="form-label" style={{ fontSize: '0.8rem' }}>
                    Target Audience
                  </label>
                  <input
                    id="target-audience"
                    type="text"
                    className="form-input"
                    placeholder="e.g. C-suite, Engineers"
                    value={targetAudience}
                    onChange={(e) => setTargetAudience(e.target.value)}
                    disabled={loading}
                  />
                </div>

                {/* Tone */}
                <div>
                  <label htmlFor="tone-select" className="form-label" style={{ fontSize: '0.8rem' }}>
                    Tone
                  </label>
                  <select
                    id="tone-select"
                    className="form-select"
                    value={tone}
                    onChange={(e) => setTone(e.target.value)}
                    disabled={loading}
                  >
                    {TONE_OPTIONS.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>

                {/* Language */}
                <div>
                  <label htmlFor="language-select" className="form-label" style={{ fontSize: '0.8rem' }}>
                    Language
                  </label>
                  <select
                    id="language-select"
                    className="form-select"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    disabled={loading}
                  >
                    {LANGUAGES.map((lang) => (
                      <option key={lang} value={lang}>{lang}</option>
                    ))}
                  </select>
                </div>

                {/* Detail Level */}
                <div>
                  <label htmlFor="detail-select" className="form-label" style={{ fontSize: '0.8rem' }}>
                    Detail Level
                  </label>
                  <select
                    id="detail-select"
                    className="form-select"
                    value={detailLevel}
                    onChange={(e) => setDetailLevel(e.target.value)}
                    disabled={loading}
                  >
                    {DETAIL_LEVELS.map((lvl) => (
                      <option key={lvl} value={lvl}>{lvl}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              className="btn-primary"
              disabled={loading || !sourceContent.trim()}
            >
              {loading ? (
                <>
                  <span className="spinner"></span>
                  <span>Transforming with Gemini...</span>
                </>
              ) : (
                <>
                  <span>{'\u{2728}'} Transform Content</span>
                </>
              )}
            </button>
          </form>
        </section>

        {/* Right Column: Results Card */}
        <section className="card">
          <div className="result-header">
            <h2 className="card-title" style={{ margin: 0 }}>
              2. Generated Artefact
            </h2>

            {result && result.transformed_content && (
              <button
                type="button"
                className={`btn-copy ${copied ? 'copied' : ''}`}
                onClick={handleCopy}
              >
                {copied ? '✓ Copied!' : '\u{1F4CB} Copy Content'}
              </button>
            )}
          </div>

          {/* Error Message */}
          {error && (
            <div className="error-banner">
              <span className="error-icon">{'\u{26A0}\u{FE0F}'}</span>
              <div>
                <strong>Error:</strong> {error}
              </div>
            </div>
          )}

          {/* Content Display */}
          {result && result.transformed_content ? (
            <div>
              <div className="result-content">
                {result.transformed_content}
              </div>

              {/* Metadata Chips */}
              <div className="metadata-container">
                <span className="metadata-chip">
                  Format: <strong>{result.output_type}</strong>
                </span>
                {result.metadata?.model && (
                  <span className="metadata-chip">
                    Model: <strong>{result.metadata.model}</strong>
                  </span>
                )}
                {result.metadata?.target_audience && (
                  <span className="metadata-chip">
                    Audience: <strong>{result.metadata.target_audience}</strong>
                  </span>
                )}
                {result.metadata?.tone && (
                  <span className="metadata-chip">
                    Tone: <strong>{result.metadata.tone}</strong>
                  </span>
                )}
                {result.metadata?.language && (
                  <span className="metadata-chip">
                    Language: <strong>{result.metadata.language}</strong>
                  </span>
                )}
                {result.metadata?.is_mock !== undefined && (
                  <span className="metadata-chip">
                    Mode: <strong>{result.metadata.is_mock ? 'Mock' : 'Real AI'}</strong>
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div className="result-empty">
              <div className="result-empty-icon">{'\u{1F4C4}'}</div>
              <p>Your transformed communication artefact will appear here.</p>
              <p style={{ fontSize: '0.85rem' }}>Select an output format and click <strong>Transform Content</strong> to begin.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
