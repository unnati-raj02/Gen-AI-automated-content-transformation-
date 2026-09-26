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

const AUDIENCE_OPTIONS = [
  'C-Suite & Executive Leadership',
  'Engineering & Technical Teams',
  'Product & Project Managers',
  'Compliance & Legal Stakeholders',
  'Marketing & Communications',
  'Investors & Financial Analysts',
  'General Audience'
];
const TONE_OPTIONS = ['Professional', 'Urgent', 'Casual', 'Inspiring', 'Informative', 'Persuasive'];
const OBJECTIVE_OPTIONS = ['Inform', 'Persuade', 'Educate', 'Call to Action', 'Inspire', 'Decision Support'];
const STYLE_OPTIONS = ['Direct & Concise', 'Analytical & Data-Driven', 'Storytelling & Narrative', 'Technical & Precise', 'Conversational'];
const DETAIL_LEVELS = ['Brief', 'Moderate', 'Detailed'];
const LANGUAGES = ['English', 'Hindi', 'Spanish', 'French', 'German'];

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const DEMO_PRESETS = [
  {
    id: 'cybersecurity',
    title: '🛡️ CyberShield Incident Pilot',
    description: 'Zero-trust architecture, 68% threat reduction, 99.4% mitigated, SOC2 Type II audit.',
    source: `Project CyberShield is an enterprise cybersecurity framework initiated in Q1 2026 to safeguard cloud infrastructure, identify zero-day vulnerabilities, and ensure zero-trust compliance across distributed multi-cloud environments. During internal pilot testing, automated detection reduced threat response times by 68%, mitigating 99.4% of simulated intrusions before lateral movement occurred. Key pillars include real-time anomaly detection, automated policy enforcement, continuous posture management, and seamless CI/CD security scanning. The platform has received SOC2 Type II certification and adheres to ISO/IEC 27001 standards.`,
    documentName: 'Project_CyberShield_Audit_Q1_2026.pdf',
    outputTypes: ['Executive Summary', 'Advisory', 'LinkedIn Post', 'Presentation'],
    audience: 'Engineering & Technical Teams',
    tone: 'Professional',
    objective: 'Inform',
    style: 'Analytical & Data-Driven',
    detail: 'Detailed'
  },
  {
    id: 'cloud_financial',
    title: '📈 Cloud ROI & Efficiency Review',
    description: 'Consolidation saving $42.5M annually, 3.8x ROI, 99.99% multi-region uptime.',
    source: `In Q3 2026, the Global Infrastructure Group completed a cloud consolidation initiative across 4 global regions, optimizing 14,000 container instances. The migration delivered $42.5M in annual recurring savings, achieved a 3.8x ROI within 9 months, and maintained 99.99% operational uptime. Carbon footprint and idle compute power consumption were reduced by 31% through automated workload scheduling. Leadership has approved Phase 2 rollout for APAC expansion.`,
    documentName: 'Cloud_Optimization_Q3_Review.docx',
    outputTypes: ['Executive Summary', 'Infographic', 'Presentation', 'LinkedIn Post'],
    audience: 'C-Suite & Executive Leadership',
    tone: 'Inspiring',
    objective: 'Decision Support',
    style: 'Direct & Concise',
    detail: 'Moderate'
  },
  {
    id: 'ai_governance',
    title: '🤖 Enterprise AI Governance Standard',
    description: 'Mandatory deployment safeguards, 99.8% PII redaction precision, 15ms latency SLAs.',
    source: `The 2026 Enterprise GenAI Governance Protocol establishes mandatory deployment safeguards across all internal and customer-facing AI agents. Protocols require automated PII redaction with 99.8% precision, mandatory human-in-the-loop signoff for contract generation, and strict 15ms latency budgets for mission-critical validation pipelines. Non-compliance results in immediate model rollback. All automated reasoning logs must be preserved for 365 days in tamper-evident storage for regulatory auditability.`,
    documentName: 'Enterprise_AI_Policy_2026.txt',
    outputTypes: ['Executive Summary', 'Advisory', 'Twitter/X Post', 'Presentation'],
    audience: 'Compliance & Legal Stakeholders',
    tone: 'Professional',
    objective: 'Educate',
    style: 'Technical & Precise',
    detail: 'Brief'
  }
];

function parsePresentationSlides(text) {
  if (!text) return [];
  const slideRegex = /(?:^|\n)(?:###?\s*)?Slide\s+(\d+)[:\s-]*(.*?)(?=(?:\n(?:###?\s*)?Slide\s+\d+|$))/gis;
  const matches = [...text.matchAll(slideRegex)];
  if (matches.length < 2) return [];

  return matches.map((m, idx) => {
    const slideNum = m[1] || `${idx + 1}`;
    const rawBody = (m[2] || '').trim();
    const lines = rawBody.split('\n').map(l => l.trim()).filter(Boolean);

    let title = `Slide ${slideNum}`;
    const bullets = [];
    let speakerNotes = '';

    if (lines.length > 0) {
      let startIdx = 0;
      const firstLine = lines[0];
      if (/^slide title:\s*/i.test(firstLine)) {
        title = firstLine.replace(/^slide title:\s*/i, '').replace(/[*_]/g, '').trim();
        startIdx = 1;
      } else if (!firstLine.startsWith('-') && !firstLine.startsWith('•') && !firstLine.startsWith('*') && !/^\d+\./.test(firstLine)) {
        title = firstLine.replace(/[*_]/g, '').trim();
        startIdx = 1;
      }

      for (let i = startIdx; i < lines.length; i++) {
        const line = lines[i];
        if (/^(?:speaker )?notes?:\s*/i.test(line)) {
          speakerNotes = lines.slice(i).join(' ').replace(/^(?:speaker )?notes?:\s*/i, '').replace(/[*_]/g, '').trim();
          break;
        } else if (line.startsWith('-') || line.startsWith('•') || line.startsWith('*')) {
          bullets.push(line.replace(/^[-•*]\s*/, '').replace(/[*_]/g, '').trim());
        } else if (/^\d+\./.test(line)) {
          bullets.push(line.replace(/^\d+\.\s*/, '').replace(/[*_]/g, '').trim());
        } else if (line) {
          bullets.push(line.replace(/[*_]/g, '').trim());
        }
      }
    }

    return { slideNum, title, bullets, speakerNotes };
  });
}

function parseInfographicData(text) {
  if (!text) return null;
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);

  let title = 'Visual Infographic Summary';
  const titleLine = lines.find(l => /^(?:catchy title|title|headline):/i.test(l));
  if (titleLine) {
    title = titleLine.replace(/^(?:catchy title|title|headline):\s*/i, '').replace(/[*_#]/g, '').trim();
  }

  const statCards = [];
  const statRegex = /^(?:[-•*]\s*)?([$€£₹]?\d+(?:\.\d+)?%?|\bQ[1-4]\s*20\d\d\b)\s*[:\-–]\s*(.+)$/i;

  for (const line of lines) {
    const match = line.match(statRegex);
    if (match) {
      statCards.push({
        value: match[1].replace(/[*_]/g, '').trim(),
        label: match[2].replace(/[*_]/g, '').trim()
      });
    }
  }

  const pillars = [];
  for (const line of lines) {
    const pMatch = line.match(/^(?:(?:\d+\.|\bPhase\s*\d+|[-•*])\s*)([A-Za-z0-9\s/_-]{3,35})[:\-–]\s*(.+)$/);
    if (pMatch && !statCards.some(s => s.label === pMatch[2])) {
      pillars.push({
        heading: pMatch[1].replace(/[*_]/g, '').trim(),
        description: pMatch[2].replace(/[*_]/g, '').trim()
      });
    }
  }

  if (statCards.length === 0 && pillars.length === 0) return null;

  return { title, statCards, pillars };
}

function App() {
  const [sourceContent, setSourceContent] = useState('');
  const [outputTypes, setOutputTypes] = useState(['Executive Summary']);
  const [targetAudience, setTargetAudience] = useState('C-Suite & Executive Leadership');
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
  const imageAutoPromptRef = useRef(null);

  // Video upload state (.mp4, .webm, .mov)
  const [videoName, setVideoName] = useState(null);
  const [videoPreview, setVideoPreview] = useState(null);
  const [videoSize, setVideoSize] = useState(null);
  const videoInputRef = useRef(null);
  const videoAutoPromptRef = useRef(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [copiedType, setCopiedType] = useState(null);

  // Stage 5: Interactive Refinement State
  const [activeRefineType, setActiveRefineType] = useState(null);
  const [refiningType, setRefiningType] = useState(null);
  const [refineInstructions, setRefineInstructions] = useState({});
  const [refineErrors, setRefineErrors] = useState({});

  // SIH Differentiation: View Modes (visual vs raw) and Slide Deck state
  const [viewModes, setViewModes] = useState({});
  const [slideIndices, setSlideIndices] = useState({});

  const toggleViewMode = (type) => {
    setViewModes((prev) => ({
      ...prev,
      [type]: prev[type] === 'raw' ? 'visual' : 'raw'
    }));
  };

  const handleNextSlide = (type, totalSlides) => {
    setSlideIndices((prev) => {
      const current = prev[type] || 0;
      return { ...prev, [type]: (current + 1) % totalSlides };
    });
  };

  const handlePrevSlide = (type, totalSlides) => {
    setSlideIndices((prev) => {
      const current = prev[type] || 0;
      return { ...prev, [type]: (current - 1 + totalSlides) % totalSlides };
    });
  };

  const handleSetSlide = (type, index) => {
    setSlideIndices((prev) => ({ ...prev, [type]: index }));
  };

  const handleApplyPreset = (preset) => {
    setSourceContent(preset.source);
    setDocumentName(preset.documentName);
    setOutputTypes(preset.outputTypes);
    setTargetAudience(preset.audience);
    setTone(preset.tone);
    setCommunicationObjective(preset.objective);
    setContentStyle(preset.style);
    setDetailLevel(preset.detail);
    setError(null);
  };

  const handleDownloadBundle = () => {
    if (!result?.outputs) return;
    const lines = [
      '# AI Content Transformation Deliverables',
      `Generated: ${new Date().toISOString()}`,
      `Model: ${result.metadata?.model || 'Gemini'}`,
      `Document Source: ${result.metadata?.document_name || 'Direct Input'}`,
      `Audience: ${result.metadata?.target_audience || 'General'} | Tone: ${result.metadata?.tone || 'Professional'}`,
      `Consolidated Call Architecture: 1 Primary Gemini Call`,
      '',
      '---',
      ''
    ];

    Object.entries(result.outputs).forEach(([type, content], idx) => {
      const prov = getOutputProvenance(type);
      lines.push(`## ${idx + 1}. ${type}`);
      if (prov?.factual_grounding?.summary) {
        lines.push(`> Factual Grounding: ${prov.factual_grounding.summary}`);
      }
      lines.push('');
      lines.push(content);
      lines.push('');
      lines.push('---');
      lines.push('');
    });

    lines.push('## Provenance & Audit Trail');
    lines.push('```json');
    lines.push(JSON.stringify(result.provenance || result.metadata?.provenance || {}, null, 2));
    lines.push('```');

    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `content_transformation_deliverables_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadProvenanceJSON = () => {
    if (!result) return;
    const provData = result.provenance || result.metadata?.provenance || {};
    const blob = new Blob([JSON.stringify(provData, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `provenance_audit_trail_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

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

  // Helper to get structured provenance for an output type
  const getOutputProvenance = (type) => {
    if (!result) return null;
    return result.provenance?.[type] || result.metadata?.provenance?.[type] || null;
  };

  // Stage 5: Refinement Handlers
  const handleToggleRefine = (type) => {
    if (refiningType !== null) return;
    if (activeRefineType === type) {
      setActiveRefineType(null);
    } else {
      setActiveRefineType(type);
      setRefineErrors((prev) => ({ ...prev, [type]: null }));
    }
  };

  const handleCancelRefine = (type) => {
    if (refiningType === type) return;
    setActiveRefineType(null);
    setRefineErrors((prev) => ({ ...prev, [type]: null }));
  };

  const handleRefineSubmit = async (type) => {
    const instruction = (refineInstructions[type] || '').trim();
    if (!instruction) {
      setRefineErrors((prev) => ({ ...prev, [type]: 'Please enter a refinement instruction.' }));
      return;
    }

    const currentOutput = result?.outputs?.[type];
    if (!currentOutput) {
      setRefineErrors((prev) => ({ ...prev, [type]: 'Current output content is missing.' }));
      return;
    }

    setRefiningType(type);
    setRefineErrors((prev) => ({ ...prev, [type]: null }));

    const payload = {
      source_content: sourceContent.trim() || `[Multimodal Analysis of ${videoName || imageName || 'attached media'}]`,
      output_type: type,
      current_output: currentOutput,
      refinement_instruction: instruction,
      target_audience: targetAudience.trim() || null,
      tone: tone || null,
      communication_objective: communicationObjective || null,
      content_style: contentStyle || null,
      language: language || 'English',
      detail_level: detailLevel || null,
      document_name: documentName || null,
      image_data: imagePreview || null,
      image_name: imageName || null,
      video_data: videoPreview || null,
      video_name: videoName || null,
    };

    try {
      const response = await fetch(`${API_BASE_URL}/refine`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Refinement failed (${response.status})`);
      }

      if (data.status !== 'success' || !data.refined_output) {
        throw new Error(data.detail || 'Refinement did not produce a valid output.');
      }

      // SELECTIVE UPDATE:
      // Update ONLY the selected output format. All other outputs remain untouched.
      setResult((prev) => {
        if (!prev) return prev;
        const updatedOutputs = {
          ...prev.outputs,
          [type]: data.refined_output,
        };

        const updatedProvItem = data.provenance || data.metadata?.provenance || {
          output_type: type,
          generation_action: 'refined',
          generation_timestamp: new Date().toISOString(),
          refinement_applied: instruction,
          validation: data.metadata?.validation,
        };

        const currentProv = prev.provenance || prev.metadata?.provenance || {};
        const updatedProvenance = {
          ...currentProv,
          [type]: updatedProvItem,
        };

        return {
          ...prev,
          outputs: updatedOutputs,
          provenance: updatedProvenance,
          metadata: {
            ...prev.metadata,
            provenance: updatedProvenance,
          },
        };
      });

      // Close refinement panel and clear instruction on success
      setActiveRefineType(null);
      setRefineInstructions((prev) => ({ ...prev, [type]: '' }));
    } catch (err) {
      console.error('Refinement error:', err);
      // Preserve previous output; only set inline error
      setRefineErrors((prev) => ({
        ...prev,
        [type]: err.message || 'Failed to refine output. Original content was preserved.',
      }));
    } finally {
      setRefiningType(null);
    }
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
      const response = await fetch(`${API_BASE_URL}/extract-text`, {
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
        const autoPrompt = `[Visual Source: ${file.name}]\nPlease analyze and transform the visual diagrams, statistics, and information in this attached image.`;
        setSourceContent(autoPrompt);
        imageAutoPromptRef.current = autoPrompt;
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
    // Only remove prompt if it matches the auto-generated prompt (i.e. user didn't modify it)
    if (imageAutoPromptRef.current && sourceContent === imageAutoPromptRef.current) {
      setSourceContent('');
    }
    imageAutoPromptRef.current = null;
  };

  // Video upload handler (.mp4, .webm, .mov)
  const handleVideoUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const extension = file.name.split('.').pop().toLowerCase();
    if (!['mp4', 'webm', 'mov'].includes(extension)) {
      setError(`Unsupported video format (.${extension}). Supported formats are: .mp4, .webm, .mov.`);
      return;
    }

    // 25MB limit for MVP base64 handling
    if (file.size > 25 * 1024 * 1024) {
      setError(`Video file is too large (${(file.size / (1024 * 1024)).toFixed(1)}MB). Please upload a video under 25MB for the MVP.`);
      return;
    }

    setError(null);
    const sizeStr = file.size > 1024 * 1024
      ? `${(file.size / (1024 * 1024)).toFixed(1)} MB`
      : `${Math.round(file.size / 1024)} KB`;

    const reader = new FileReader();
    reader.onload = () => {
      setVideoPreview(reader.result);
      setVideoName(file.name);
      setVideoSize(sizeStr);
      if (!sourceContent.trim()) {
        const autoPrompt = `[Video Source: ${file.name}]\nPlease analyze and transform the visual scenes, demonstrations, dialogue, and key topics from this attached video.`;
        setSourceContent(autoPrompt);
        videoAutoPromptRef.current = autoPrompt;
      }
    };
    reader.onerror = () => {
      setError('Failed to read the selected video file.');
    };
    reader.readAsDataURL(file);
  };

  const handleClearVideo = () => {
    setVideoPreview(null);
    setVideoName(null);
    setVideoSize(null);
    if (videoInputRef.current) {
      videoInputRef.current.value = '';
    }
    // Only remove prompt if it matches the auto-generated prompt (i.e. user didn't modify it)
    if (videoAutoPromptRef.current && sourceContent === videoAutoPromptRef.current) {
      setSourceContent('');
    }
    videoAutoPromptRef.current = null;
  };

  const handleTransform = async (e) => {
    e.preventDefault();

    if (!sourceContent.trim() && !imagePreview && !videoPreview) {
      setError('Please provide source content, or upload a document, image, or video to transform.');
      return;
    }

    if (outputTypes.length === 0) {
      setError('Please select at least one output format.');
      return;
    }

    setLoading(true);
    setError(null);
    setActiveRefineType(null);
    setRefiningType(null);
    setRefineErrors({});

    const payload = {
      source_content: sourceContent.trim() || `[Multimodal Analysis of ${videoName || imageName || 'attached media'}]`,
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
      video_data: videoPreview || null,
      video_name: videoName || null,
    };

    try {
      const response = await fetch(`${API_BASE_URL}/transform`, {
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

  // Robust clipboard copy with modern API and textarea fallback
  const copyToClipboard = async (text) => {
    if (!text) return false;

    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (err) {
        console.warn('navigator.clipboard write failed, using fallback:', err);
      }
    }

    try {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '-9999px';
      textArea.style.top = '-9999px';
      textArea.setAttribute('readonly', '');
      document.body.appendChild(textArea);
      textArea.select();
      const successful = document.execCommand('copy');
      document.body.removeChild(textArea);
      return successful;
    } catch (fallbackErr) {
      console.error('Clipboard copy failed:', fallbackErr);
      return false;
    }
  };

  // Copy individual output content
  const handleCopy = async (text, typeKey) => {
    const success = await copyToClipboard(text);
    if (success) {
      setCopiedType(typeKey);
      setTimeout(() => setCopiedType(null), 2000);
    }
  };

  // Copy all generated outputs combined
  const handleCopyAll = async () => {
    if (result && result.outputs) {
      const allText = Object.entries(result.outputs)
        .map(([type, text]) => `=== ${type.toUpperCase()} ===\n\n${text}`)
        .join('\n\n---\n\n');
      const success = await copyToClipboard(allText);
      if (success) {
        setCopiedType('all');
        setTimeout(() => setCopiedType(null), 2000);
      }
    }
  };

  // Clear source text only (preserves attached document/image/video badges)
  const handleClearText = () => {
    setSourceContent('');
    imageAutoPromptRef.current = null;
    videoAutoPromptRef.current = null;
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

          {/* 1-Click Enterprise Demo Presets */}
          <div className="demo-presets-container">
            <div className="demo-presets-label">
              <span>⚡ Enterprise Demo Presets:</span>
            </div>
            <div className="demo-presets-buttons">
              {DEMO_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  className="btn-preset"
                  onClick={() => handleApplyPreset(preset)}
                  disabled={loading || extracting || refiningType !== null}
                  title={preset.description}
                >
                  <span>{preset.title}</span>
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleTransform}>
            {/* Source Content & Document / Image Upload */}
            <div className="form-group">
              <div className="source-label-row">
                <label htmlFor="source-content" className="form-label" style={{ marginBottom: 0 }}>
                  <span>Source Content *</span>
                  <span className="char-counter">
                    {sourceContent.length} characters
                    {sourceContent.length > 0 && (
                      <button
                        type="button"
                        className="btn-clear-text"
                        onClick={handleClearText}
                        disabled={loading || extracting}
                        title="Clear source text only"
                      >
                        Clear
                      </button>
                    )}
                  </span>
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
                  <div className="video-upload-wrapper">
                    <input
                      type="file"
                      ref={videoInputRef}
                      onChange={handleVideoUpload}
                      accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
                      style={{ display: 'none' }}
                      id="video-upload-input"
                      disabled={loading || extracting}
                    />
                    <label htmlFor="video-upload-input" className="btn-video-upload">
                      🎥 Upload Video
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

              {videoPreview && (
                <div className="video-loaded-badge">
                  <div className="video-loaded-info">
                    <div className="video-preview-wrapper">
                      <video src={videoPreview} className="video-thumb" muted preload="metadata" />
                      <span className="video-icon-overlay">▶</span>
                    </div>
                    <div className="video-loaded-meta">
                      <span className="video-name">🎥 <strong>{videoName}</strong> {videoSize && <span className="video-size-tag">({videoSize})</span>}</span>
                      <span className="video-desc">Video attached for multimodal AI understanding (.mp4, .webm, .mov)</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-video-clear"
                    onClick={handleClearVideo}
                    disabled={loading || extracting}
                    title="Remove attached video"
                  >
                    ✕
                  </button>
                </div>
              )}

              <textarea
                id="source-content"
                className="form-textarea"
                placeholder="Paste or write notes, upload a document (.txt, .pdf, .docx), attach an image, or upload a video (.mp4, .webm, .mov)..."
                value={sourceContent}
                onChange={(e) => setSourceContent(e.target.value)}
                disabled={loading || extracting}
                required={!imagePreview && !videoPreview}
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
                  <select
                    id="target-audience"
                    className="form-select"
                    value={targetAudience}
                    onChange={(e) => setTargetAudience(e.target.value)}
                    disabled={loading}
                  >
                    {AUDIENCE_OPTIONS.map((aud) => (
                      <option key={aud} value={aud}>{aud}</option>
                    ))}
                  </select>
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
              disabled={loading || extracting || refiningType !== null || (!sourceContent.trim() && !imagePreview && !videoPreview) || outputTypes.length === 0}
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

            {hasOutputs && (
              <div className="export-actions-group">
                <button
                  type="button"
                  className="btn-export-bundle"
                  onClick={handleDownloadBundle}
                  title="Download all deliverables formatted as a complete Markdown bundle"
                >
                  📥 Export Bundle (.md)
                </button>
                <button
                  type="button"
                  className="btn-export-json"
                  onClick={handleDownloadProvenanceJSON}
                  title="Download machine-readable provenance and audit trail"
                >
                  🛡️ Audit JSON
                </button>
                {Object.keys(result.outputs).length > 1 && (
                  <button
                    type="button"
                    className={`btn-copy ${copiedType === 'all' ? 'copied' : ''}`}
                    onClick={handleCopyAll}
                  >
                    {copiedType === 'all' ? '\u{2713} All Copied!' : '\u{1F4CB} Copy All'}
                  </button>
                )}
              </div>
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
                {Object.entries(result.outputs).map(([type, content]) => {
                  const outputProv = getOutputProvenance(type);
                  const isRefiningThis = refiningType === type;
                  const isRefineOpen = activeRefineType === type;

                  return (
                    <div key={type} className={`output-card ${isRefiningThis ? 'card-refining' : ''}`}>
                      <div className="output-card-header">
                        <div className="output-card-title-group">
                          <div className="output-card-title">
                            <span className="output-type-icon">{getTypeIcon(type)}</span>
                            <span>{type}</span>
                          </div>
                          <div className="output-badges-group">
                            {outputProv?.factual_grounding?.is_grounded && outputProv?.factual_grounding?.verified_count > 0 && (
                              <span
                                className="badge-provenance badge-grounded"
                                title={outputProv.factual_grounding.summary || 'Factual grounding verified'}
                              >
                                🛡️ {outputProv.factual_grounding.verified_count}/{outputProv.factual_grounding.total_source_facts || outputProv.factual_grounding.verified_count} Grounded
                              </span>
                            )}
                            {outputProv?.factual_grounding && !outputProv.factual_grounding.is_grounded && (
                              <span
                                className="badge-provenance badge-ungrounded"
                                title={outputProv.factual_grounding.summary || 'Ungrounded content detected'}
                              >
                                🚫 Ungrounded
                              </span>
                            )}
                            {!outputProv?.factual_grounding?.is_grounded && outputProv?.factual_grounding?.unverified_metrics?.length > 0 && (
                              <span
                                className="badge-provenance badge-unverified"
                                title={`Unverified metrics: ${outputProv.factual_grounding.unverified_metrics.join(', ')}`}
                              >
                                ⚠️ {outputProv.factual_grounding.unverified_metrics.length} Unverified Metric ({outputProv.factual_grounding.unverified_metrics.join(', ')})
                              </span>
                            )}
                            {!outputProv?.factual_grounding?.is_grounded && outputProv?.factual_grounding?.unsupported_events?.length > 0 && (
                              <span
                                className="badge-provenance badge-unverified"
                                title={`Unsupported events: ${outputProv.factual_grounding.unsupported_events.join(', ')}`}
                              >
                                ⚠️ Unsupported Event: {outputProv.factual_grounding.unsupported_events.join(', ')}
                              </span>
                            )}
                            {!outputProv?.factual_grounding?.is_grounded && outputProv?.factual_grounding?.unsupported_entities?.length > 0 && (
                              <span
                                className="badge-provenance badge-unverified"
                                title={`Unsupported entities: ${outputProv.factual_grounding.unsupported_entities.join(', ')}`}
                              >
                                ⚠️ Unsupported Entity: {outputProv.factual_grounding.unsupported_entities.join(', ')}
                              </span>
                            )}
                            {(outputProv?.generation_action === 'recovered' || outputProv?.recovery_attempted) && (
                              <span
                                className="badge-provenance badge-recovered"
                                title="Recovered via targeted recovery"
                              >
                                🔄 Self-Healed
                              </span>
                            )}
                            {(outputProv?.generation_action === 'refined' || outputProv?.refinement_applied) && (
                              <span
                                className="badge-provenance badge-refined"
                                title={`Refined: "${outputProv.refinement_applied || ''}"`}
                              >
                                ✨ Refined
                              </span>
                            )}
                            {(outputProv?.validation?.valid ?? outputProv?.validation?.is_valid) ? (
                              <span
                                className="badge-provenance badge-valid"
                                title="Quality validation passed"
                              >
                                ✓ Validated
                              </span>
                            ) : outputProv?.validation?.severity === 'warning' ? (
                              <span
                                className="badge-provenance badge-warning"
                                title={`Notice: ${outputProv.validation?.issues?.join(', ') || 'Validation warning'}`}
                              >
                                ⚠️ Notice
                              </span>
                            ) : null}
                          </div>
                        </div>

                        <div className="output-card-actions">
                          <button
                            type="button"
                            className={`btn-refine ${isRefineOpen ? 'active' : ''}`}
                            onClick={() => handleToggleRefine(type)}
                            disabled={refiningType !== null || loading}
                            title="Refine this output with AI"
                          >
                            ✨ Refine
                          </button>
                          <button
                            type="button"
                            className={`btn-copy ${copiedType === type ? 'copied' : ''}`}
                            onClick={() => handleCopy(content, type)}
                            disabled={isRefiningThis}
                          >
                            {copiedType === type ? '✓ Copied!' : '📋 Copy'}
                          </button>
                        </div>
                      </div>

                      {/* Interactive Refinement Panel */}
                      {isRefineOpen && (
                        <div className="refine-panel">
                          <div className="refine-panel-header">
                            <span className="refine-panel-title">✨ Refine {type} with AI</span>
                            <span className="refine-hint">Instruct Gemini to adjust tone, length, structure, or focus</span>
                          </div>
                          <textarea
                            className="refine-textarea"
                            placeholder={`e.g. Make this ${type.toLowerCase()} more concise and professional, highlight key data, or adapt for a non-technical audience...`}
                            value={refineInstructions[type] || ''}
                            onChange={(e) => {
                              const val = e.target.value;
                              setRefineInstructions((prev) => ({ ...prev, [type]: val }));
                              if (refineErrors[type]) {
                                setRefineErrors((prev) => ({ ...prev, [type]: null }));
                              }
                            }}
                            disabled={isRefiningThis}
                            rows={3}
                            autoFocus
                          />
                          {refineErrors[type] && (
                            <div className="refine-error-inline">
                              <span className="error-icon">⚠️</span>
                              <span>{refineErrors[type]}</span>
                            </div>
                          )}
                          <div className="refine-actions-row">
                            <button
                              type="button"
                              className="btn-refine-cancel"
                              onClick={() => handleCancelRefine(type)}
                              disabled={isRefiningThis}
                            >
                              Cancel
                            </button>
                            <button
                              type="button"
                              className="btn-refine-submit"
                              onClick={() => handleRefineSubmit(type)}
                              disabled={isRefiningThis || !(refineInstructions[type] || '').trim()}
                            >
                              {isRefiningThis ? (
                                <>
                                  <span className="spinner-sm"></span>
                                  <span>Refining...</span>
                                </>
                              ) : (
                                <span>Apply Refinement</span>
                              )}
                            </button>
                          </div>
                        </div>
                      )}

                      <div className="result-content output-content">
                        {isRefiningThis && (
                          <div className="refine-loading-banner">
                            <span className="spinner-sm"></span>
                            <span>Refining {type} with AI...</span>
                          </div>
                        )}
                        {/* Presentation Slide Deck Interactive View */}
                        {type === 'Presentation' && (() => {
                          const slides = parsePresentationSlides(content);
                          if (slides.length < 2) return null;
                          const isVisual = viewModes[type] !== 'raw';
                          const currentIndex = slideIndices[type] || 0;
                          const activeSlide = slides[currentIndex] || slides[0];

                          return (
                            <div style={{ marginBottom: '0.75rem' }}>
                              <div className="view-mode-bar">
                                <span className="view-mode-title">📊 Slide Deck View ({slides.length} Slides)</span>
                                <div className="view-mode-toggle">
                                  <button
                                    type="button"
                                    className={`btn-toggle-view ${isVisual ? 'active' : ''}`}
                                    onClick={() => toggleViewMode(type)}
                                  >
                                    Slide Deck
                                  </button>
                                  <button
                                    type="button"
                                    className={`btn-toggle-view ${!isVisual ? 'active' : ''}`}
                                    onClick={() => toggleViewMode(type)}
                                  >
                                    Raw Text
                                  </button>
                                </div>
                              </div>

                              {isVisual && (
                                <div className="slide-deck-container">
                                  <div className="slide-card">
                                    <div className="slide-card-header">
                                      <span className="slide-index-badge">Slide {currentIndex + 1} of {slides.length}</span>
                                    </div>
                                    <div className="slide-title">{activeSlide.title}</div>
                                    {activeSlide.bullets.length > 0 && (
                                      <ul className="slide-bullets">
                                        {activeSlide.bullets.map((b, bIdx) => (
                                          <li key={bIdx} className="slide-bullet-item">
                                            <span className="slide-bullet-icon">▸</span>
                                            <span>{b}</span>
                                          </li>
                                        ))}
                                      </ul>
                                    )}
                                    {activeSlide.speakerNotes && (
                                      <div className="slide-notes-drawer">
                                        <span className="slide-notes-label">🎙️ Speaker Notes</span>
                                        <span>{activeSlide.speakerNotes}</span>
                                      </div>
                                    )}
                                  </div>
                                  <div className="slide-nav-bar">
                                    <button
                                      type="button"
                                      className="btn-slide-nav"
                                      onClick={() => handlePrevSlide(type, slides.length)}
                                      disabled={slides.length <= 1}
                                    >
                                      ◀ Previous
                                    </button>
                                    <div className="slide-dots">
                                      {slides.map((_, sIdx) => (
                                        <span
                                          key={sIdx}
                                          className={`slide-dot ${sIdx === currentIndex ? 'active' : ''}`}
                                          onClick={() => handleSetSlide(type, sIdx)}
                                          title={`Slide ${sIdx + 1}`}
                                        />
                                      ))}
                                    </div>
                                    <button
                                      type="button"
                                      className="btn-slide-nav"
                                      onClick={() => handleNextSlide(type, slides.length)}
                                      disabled={slides.length <= 1}
                                    >
                                      Next ▶
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })()}

                        {/* Infographic Visual Dashboard View */}
                        {type === 'Infographic' && (() => {
                          const infoData = parseInfographicData(content);
                          if (!infoData) return null;
                          const isVisual = viewModes[type] !== 'raw';

                          return (
                            <div style={{ marginBottom: '0.75rem' }}>
                              <div className="view-mode-bar">
                                <span className="view-mode-title">📈 Metric Dashboard View</span>
                                <div className="view-mode-toggle">
                                  <button
                                    type="button"
                                    className={`btn-toggle-view ${isVisual ? 'active' : ''}`}
                                    onClick={() => toggleViewMode(type)}
                                  >
                                    Dashboard
                                  </button>
                                  <button
                                    type="button"
                                    className={`btn-toggle-view ${!isVisual ? 'active' : ''}`}
                                    onClick={() => toggleViewMode(type)}
                                  >
                                    Raw Text
                                  </button>
                                </div>
                              </div>

                              {isVisual && (
                                <div className="infographic-dashboard">
                                  <div className="infographic-title-banner">
                                    <span>📊</span>
                                    <span>{infoData.title}</span>
                                  </div>

                                  {infoData.statCards.length > 0 && (
                                    <div className="infographic-stats-grid">
                                      {infoData.statCards.map((stat, sIdx) => (
                                        <div key={sIdx} className="stat-card">
                                          <div className="stat-value">{stat.value}</div>
                                          <div className="stat-label">{stat.label}</div>
                                        </div>
                                      ))}
                                    </div>
                                  )}

                                  {infoData.pillars.length > 0 && (
                                    <div className="infographic-pillars-grid">
                                      {infoData.pillars.map((pillar, pIdx) => (
                                        <div key={pIdx} className="pillar-card">
                                          <div className="pillar-heading">
                                            <span>📌</span>
                                            <span>{pillar.heading}</span>
                                          </div>
                                          <div className="pillar-desc">{pillar.description}</div>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })()}

                        {/* Standard Raw Text Rendering for Non-Visual or when Raw view selected */}
                        {((type !== 'Presentation' && type !== 'Infographic') ||
                          (type === 'Presentation' && (viewModes[type] === 'raw' || parsePresentationSlides(content).length < 2)) ||
                          (type === 'Infographic' && (viewModes[type] === 'raw' || !parseInfographicData(content)))) && (
                          <div style={{ whiteSpace: 'pre-wrap' }}>{content}</div>
                        )}
                      </div>
                    </div>
                  );
                })}
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
                {result.metadata?.video_name && (
                  <span className="metadata-chip">
                    Video: <strong>{result.metadata.video_name}</strong>
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
                {result.provenance && Object.values(result.provenance).some((p) => p.generation_action === 'refined' || p.refinement_applied) && (
                  <span className="metadata-chip" style={{ borderColor: 'rgba(99, 102, 241, 0.4)', color: '#c7d2fe' }}>
                    Refinement: <strong>Active</strong>
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
