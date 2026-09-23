import React, { useState, useRef } from 'react';
import './App.css';

const OUTPUT_TYPES = [
  { id: 'Executive Summary', label: 'Executive Summary', icon: '\u{1F4CB}' },
  { id: 'Advisory', label: 'Advisory', icon: '\u{26A0}\u{FE0F}' },
  { id: 'LinkedIn Post', label: 'LinkedIn Post', icon: '\u{1F680}' },
  { id: 'Twitter/X Post', label: 'Twitter/X Post', icon: '\u{1F4AC}' },
  { id: 'Infographic', label: 'Infographic', icon: '\u{1F4CA}' },
  { id: 'Presentation', label: 'Presentation', icon: '\u{1F5A5}\u{FE0F}' },
  { id: 'Video Package', label: 'Video Package', icon: '\u{1F3AC}' },
];

const TONE_OPTIONS = ['Professional', 'Urgent', 'Casual', 'Inspiring', 'Informative', 'Persuasive'];
const OBJECTIVE_OPTIONS = ['Inform', 'Persuade', 'Educate', 'Call to Action', 'Inspire', 'Decision Support'];
const STYLE_OPTIONS = ['Direct & Concise', 'Analytical & Data-Driven', 'Storytelling & Narrative', 'Technical & Precise', 'Conversational'];
const DETAIL_LEVELS = ['Brief', 'Moderate', 'Detailed'];
const LANGUAGES = ['English', 'Hindi', 'Spanish', 'French', 'German'];

function App() {
  const [sourceContent, setSourceContent] = useState('');
  const [outputTypes, setOutputTypes] = useState(['Executive Summary']);
  const [targetAudience, setTargetAudience] = useState('C-suite Executives');
  const [tone, setTone] = useState('Professional');
  const [communicationObjective, setCommunicationObjective] = useState('Inform');
  const [contentStyle, setContentStyle] = useState('Direct & Concise');
  const [language, setLanguage] = useState('English');
  const [detailLevel, setDetailLevel] = useState('Brief');
  const [documentName, setDocumentName] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const fileInputRef = useRef(null);

  // Image upload state
  const [imageName, setImageName] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const imageInputRef = useRef(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [copiedType, setCopiedType] = useState(null);

  // Toggle selection for multiple output types
  const toggleOutputType = (id) => {
    if (outputTypes.includes(id)) {
      setOutputTypes(outputTypes.filter((t) => t !== id));
    } else {
      setOutputTypes([...outputTypes, id]);
    }
  };

  // Helper to retrieve icon for each output type
  const getTypeIcon = (typeName) => {
    const matched = OUTPUT_TYPES.find((t) => t.id === typeName || t.label === typeName);
    return matched ? matched.icon : '\u{1F4C4}';
  };

  // Document upload handler (.txt, .pdf, .docx support)
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const extension = file.name.split('.').pop().toLowerCase();
    if (!['txt', 'md', 'pdf', 'docx'].includes(extension)) {
      setError(`Unsupported document format (.${extension}). Supported formats are: .txt, .pdf, .docx.`);
      return;
    }

    setExtracting(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://127.0.0.1:8000/extract-text', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Extraction failed (${response.status})`);
      }

      setSourceContent(data.extracted_text);
      setDocumentName(file.name);
    } catch (err) {
      console.error('Extraction error:', err);
      setError(err.message || 'Failed to extract text from the uploaded document.');
    } finally {
      setExtracting(false);
    }
  };

  const handleClearDocument = () => {
    setDocumentName(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Image upload handler (.png, .jpg, .jpeg, .webp, .gif)
  const handleImageUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const extension = file.name.split('.').pop().toLowerCase();
    if (!['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(extension)) {
      setError(`Unsupported image format (.${extension}). Supported formats are: .png, .jpg, .jpeg, .webp, .gif.`);
      return;
    }

    setError(null);
    const reader = new FileReader();
    reader.onload = () => {
      setImagePreview(reader.result);
      setImageName(file.name);
      if (!sourceContent.trim()) {
        setSourceContent(`[Visual Source: ${file.name}]\nPlease analyze and transform the visual diagrams, statistics, and information in this attached image.`);
      }
    };
    reader.onerror = () => {
      setError('Failed to read the selected image file.');
    };
    reader.readAsDataURL(file);
  };

  const handleClearImage = () => {
    setImagePreview(null);
    setImageName(null);
    if (imageInputRef.current) {
      imageInputRef.current.value = '';
    }
  };

  const handleTransform = async (e) => {
    e.preventDefault();

    if (!sourceContent.trim() && !imagePreview) {
      setError('Please provide source content or upload an image to transform.');
      return;
    }

    if (outputTypes.length === 0) {
      setError('Please select at least one output format.');
      return;
    }

    setLoading(true);
    setError(null);

    const payload = {
      source_content: sourceContent.trim() || `[Visual Analysis of ${imageName || 'attached image'}]`,
      output_types: outputTypes,
      target_audience: targetAudience.trim() || null,
      tone: tone || null,
      communication_objective: communicationObjective || null,
      content_style: contentStyle || null,
      language: language || 'English',
      detail_level: detailLevel || null,
      document_name: documentName || null,
      image_data: imagePreview || null,
      image_name: imageName || null,
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

  // Copy individual output content
  const handleCopy = (text, typeKey) => {
    if (text) {
      navigator.clipboard.writeText(text);
      setCopiedType(typeKey);
      setTimeout(() => setCopiedType(null), 2000);
    }
  };

  // Copy all generated outputs combined
  const handleCopyAll = () => {
    if (result && result.outputs) {
      const allText = Object.entries(result.outputs)
        .map(([type, text]) => `=== ${type.toUpperCase()} ===\n\n${text}`)
        .join('\n\n---\n\n');
      navigator.clipboard.writeText(allText);
      setCopiedType('all');
      setTimeout(() => setCopiedType(null), 2000);
    }
  };

  const hasOutputs = result && result.outputs && Object.keys(result.outputs).length > 0;

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="badge">
          <span className="badge-dot"></span>
          AI Content Transformer · SIH MVP
        </div>
        <h1>Transform Source Into Impact</h1>
        <p>Convert raw information into structured Executive Summaries, Advisories, Social Posts, Infographics, Presentations, and Video Packages using Gemini.</p>
      </header>

      {/* Main Grid */}
      <main className="main-layout">
        {/* Left Column: Form Controls */}
        <section className="card">
          <h2 className="card-title">1. Source & Configuration</h2>

          <form onSubmit={handleTransform}>
            {/* Source Content & Document / Image Upload */}
            <div className="form-group">
              <div className="source-label-row">
                <label htmlFor="source-content" className="form-label" style={{ marginBottom: 0 }}>
                  <span>Source Content *</span>
                  <span className="char-counter">{sourceContent.length} characters</span>
                </label>
                <div className="upload-buttons-group">
                  <div className="doc-upload-wrapper">
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileUpload}
                      accept=".txt,.md,.pdf,.docx"
                      style={{ display: 'none' }}
                      id="doc-upload-input"
                      disabled={loading || extracting}
                    />
                    <label htmlFor="doc-upload-input" className={`btn-doc-upload ${extracting ? 'loading' : ''}`}>
                      {extracting ? '⏳ Extracting...' : '📄 Upload Doc'}
                    </label>
                  </div>
                  <div className="img-upload-wrapper">
                    <input
                      type="file"
                      ref={imageInputRef}
                      onChange={handleImageUpload}
                      accept="image/png,image/jpeg,image/webp,image/gif"
                      style={{ display: 'none' }}
                      id="img-upload-input"
                      disabled={loading || extracting}
                    />
                    <label htmlFor="img-upload-input" className="btn-img-upload">
                      🖼️ Upload Image
                    </label>
                  </div>
                </div>
              </div>

              {documentName && (
                <div className="doc-loaded-badge">
                  <span>📎 Document loaded: <strong>{documentName}</strong></span>
                  <button
                    type="button"
                    className="btn-doc-clear"
                    onClick={handleClearDocument}
                    disabled={loading || extracting}
                    title="Clear document badge"
                  >
                    ✕
                  </button>
                </div>
              )}

              {imagePreview && (
                <div className="img-loaded-badge">
                  <div className="img-loaded-info">
                    <img src={imagePreview} alt="Uploaded source" className="img-thumb" />
                    <div className="img-loaded-meta">
                      <span className="img-name">🖼️ <strong>{imageName}</strong></span>
                      <span className="img-desc">Image attached for multimodal AI understanding</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-img-clear"
                    onClick={handleClearImage}
                    disabled={loading || extracting}
                    title="Remove attached image"
                  >
                    ✕
                  </button>
                </div>
              )}

              <textarea
                id="source-content"
                className="form-textarea"
                placeholder="Paste or write notes, upload a document (.txt, .pdf, .docx), or attach an image (.png, .jpg, .webp)..."
                value={sourceContent}
                onChange={(e) => setSourceContent(e.target.value)}
                disabled={loading || extracting}
                required={!imagePreview}
              />
            </div>

            {/* Multi-Select Output Types Selector */}
            <div className="form-group">
              <label className="form-label">
                <span>Output Formats * (Select one or more)</span>
                <span className="char-counter">{outputTypes.length} selected</span>
              </label>
              <div className="output-type-grid">
                {OUTPUT_TYPES.map((type) => {
                  const isSelected = outputTypes.includes(type.id);
                  return (
                    <button
                      key={type.id}
                      type="button"
                      className={`output-type-btn ${isSelected ? 'active' : ''}`}
                      onClick={() => toggleOutputType(type.id)}
                      disabled={loading}
                    >
                      <div>
                        <span style={{ marginRight: '6px' }}>{isSelected ? '\u{2713}' : '+'}</span>
                        {type.icon} {type.label}
                      </div>
                    </button>
                  );
                })}
              </div>
              {outputTypes.length === 0 && (
                <p style={{ color: 'var(--error)', fontSize: '0.8rem', marginTop: '0.5rem' }}>
                  Select at least one format to continue.
                </p>
              )}
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

                {/* Communication Objective */}
                <div>
                  <label htmlFor="objective-select" className="form-label" style={{ fontSize: '0.8rem' }}>
                    Communication Objective
                  </label>
                  <select
                    id="objective-select"
                    className="form-select"
                    value={communicationObjective}
                    onChange={(e) => setCommunicationObjective(e.target.value)}
                    disabled={loading}
                  >
                    {OBJECTIVE_OPTIONS.map((obj) => (
                      <option key={obj} value={obj}>{obj}</option>
                    ))}
                  </select>
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

                {/* Content Style */}
                <div>
                  <label htmlFor="style-select" className="form-label" style={{ fontSize: '0.8rem' }}>
                    Content Style
                  </label>
                  <select
                    id="style-select"
                    className="form-select"
                    value={contentStyle}
                    onChange={(e) => setContentStyle(e.target.value)}
                    disabled={loading}
                  >
                    {STYLE_OPTIONS.map((s) => (
                      <option key={s} value={s}>{s}</option>
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
              disabled={loading || extracting || (!sourceContent.trim() && !imagePreview) || outputTypes.length === 0}
            >
              {loading ? (
                <>
                  <span className="spinner"></span>
                  <span>Transforming with Gemini...</span>
                </>
              ) : (
                <>
                  <span>{'\u{2728}'} Transform Content ({outputTypes.length})</span>
                </>
              )}
            </button>
          </form>
        </section>

        {/* Right Column: Results Card */}
        <section className="card">
          <div className="result-header">
            <h2 className="card-title" style={{ margin: 0 }}>
              2. Generated Artefacts
            </h2>

            {hasOutputs && Object.keys(result.outputs).length > 1 && (
              <button
                type="button"
                className={`btn-copy ${copiedType === 'all' ? 'copied' : ''}`}
                onClick={handleCopyAll}
              >
                {copiedType === 'all' ? '\u{2713} All Copied!' : '\u{1F4CB} Copy All'}
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

          {/* Multiple Outputs Display */}
          {hasOutputs ? (
            <div>
              <div className="outputs-list">
                {Object.entries(result.outputs).map(([type, content]) => (
                  <div key={type} className="output-card">
                    <div className="output-card-header">
                      <div className="output-card-title">
                        <span className="output-type-icon">{getTypeIcon(type)}</span>
                        <span>{type}</span>
                      </div>
                      <button
                        type="button"
                        className={`btn-copy ${copiedType === type ? 'copied' : ''}`}
                        onClick={() => handleCopy(content, type)}
                      >
                        {copiedType === type ? '\u{2713} Copied!' : '\u{1F4CB} Copy'}
                      </button>
                    </div>
                    <div className="result-content output-content">
                      {content}
                    </div>
                  </div>
                ))}
              </div>

              {/* Metadata Chips */}
              <div className="metadata-container">
                <span className="metadata-chip">
                  Outputs: <strong>{Object.keys(result.outputs).length} generated</strong>
                </span>
                {result.metadata?.model && (
                  <span className="metadata-chip">
                    Model: <strong>{result.metadata.model}</strong>
                  </span>
                )}
                {result.metadata?.document_name && (
                  <span className="metadata-chip">
                    Document: <strong>{result.metadata.document_name}</strong>
                  </span>
                )}
                {result.metadata?.image_name && (
                  <span className="metadata-chip">
                    Image: <strong>{result.metadata.image_name}</strong>
                  </span>
                )}
                {result.metadata?.target_audience && (
                  <span className="metadata-chip">
                    Audience: <strong>{result.metadata.target_audience}</strong>
                  </span>
                )}
                {result.metadata?.communication_objective && (
                  <span className="metadata-chip">
                    Objective: <strong>{result.metadata.communication_objective}</strong>
                  </span>
                )}
                {result.metadata?.tone && (
                  <span className="metadata-chip">
                    Tone: <strong>{result.metadata.tone}</strong>
                  </span>
                )}
                {result.metadata?.content_style && (
                  <span className="metadata-chip">
                    Style: <strong>{result.metadata.content_style}</strong>
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
              <p>Your transformed communication artefacts will appear here.</p>
              <p style={{ fontSize: '0.85rem' }}>Select one or more output formats and click <strong>Transform Content</strong> to begin.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
