/**
 * Studio — halaman untuk membuat dan mem-posting konten LinkedIn (Module A & B).
 * Requirements: 2.1–2.11, 3.1–3.7, 10.1–10.6
 */

import React, { useState } from 'react';
import { AlertCircle, CheckCircle2 } from 'lucide-react';

import { DashboardLayout } from '@/components/templates';
import { StudioLayout } from '@/components/templates';
import { ContentForm, PromoForm, ContentPreview } from '@/components/organisms';
import { ContentVariantCard } from '@/components/molecules';
import { Spinner } from '@/components/atoms';
import { generateContent, createPost, publishPost } from '@/lib/api';
import { useBotProgress } from '@/hooks';
import type { Post } from '@/types';
import type { ContentVariant } from '@/components/molecules/ContentVariantCard';

import type { ContentFormValues } from '@/components/organisms/ContentForm';
import type { PromoFormValues } from '@/components/organisms/PromoForm';

type Tab = 'konten' | 'promo';

function BotProgressBar() {
  const { isRunning, steps, error, currentModule } = useBotProgress();

  if (!isRunning && steps.length === 0 && !error) return null;

  return (
    <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 space-y-2">
      <div className="flex items-center gap-2">
        {isRunning && <Spinner size="sm" />}
        {error && <AlertCircle size={16} className="text-red-500" />}
        {!isRunning && !error && <CheckCircle2 size={16} className="text-green-500" />}
        <span className="text-sm font-medium text-blue-800">
          {isRunning
            ? `Bot berjalan (Module ${currentModule})...`
            : error
            ? 'Bot error'
            : 'Bot selesai'}
        </span>
      </div>
      {steps.slice(-5).map((step, i) => (
        <p key={i} className="text-xs text-blue-700 pl-6">
          {step.message}
        </p>
      ))}
      {error && <p className="text-xs text-red-600 pl-6">{error}</p>}
    </div>
  );
}

export default function StudioPage() {
  const [activeTab, setActiveTab] = useState<Tab>('konten');
  const [generating, setGenerating] = useState(false);
  const [posting, setPosting] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [variants, setVariants] = useState<Post[]>([]);
  const [selectedIdx, setSelectedIdx] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const selectedPost = variants[selectedIdx] ?? null;

  const handleContentSubmit = async (values: ContentFormValues) => {
    setGenerating(true);
    setErrorMsg(null);
    setVariants([]);
    setSelectedIdx(0);
    try {
      const res = await generateContent({
        content_type: values.content_type as Post['content_type'],
        topic: values.topic,
        language: 'indonesia',
        include_image: values.generate_image,
      });
      setVariants(res.variants);
    } catch {
      setErrorMsg('Gagal generate konten. Pastikan backend berjalan.');
    } finally {
      setGenerating(false);
    }
  };

  const handlePromoSubmit = async (values: PromoFormValues) => {
    setGenerating(true);
    setErrorMsg(null);
    setVariants([]);
    setSelectedIdx(0);
    try {
      const res = await generateContent({
        content_type: 'promo',
        topic: values.description,
        language: 'indonesia',
      });
      setVariants(res.variants);
    } catch {
      setErrorMsg('Gagal generate konten promosi. Pastikan backend berjalan.');
    } finally {
      setGenerating(false);
    }
  };

  const handlePost = async () => {
    if (!selectedPost) return;
    setPosting(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      let postId = selectedPost.id;
      if (!postId) {
        const created = await createPost({
          content: selectedPost.content,
          content_type: selectedPost.content_type,
          tone: selectedPost.tone ?? undefined,
          title: selectedPost.title ?? undefined,
        });
        postId = created.id;
      }
      await publishPost(postId);
      setSuccessMsg('Post berhasil dikirim ke bot untuk diposting ke LinkedIn!');
    } catch {
      setErrorMsg('Gagal memulai posting. Pastikan HP terhubung.');
    } finally {
      setPosting(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!selectedPost) return;
    setSavingDraft(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await createPost({
        content: selectedPost.content,
        content_type: selectedPost.content_type,
        tone: selectedPost.tone ?? undefined,
        title: selectedPost.title ?? undefined,
      });
      setSuccessMsg('Draft berhasil disimpan!');
    } catch {
      setErrorMsg('Gagal menyimpan draft.');
    } finally {
      setSavingDraft(false);
    }
  };

  const handleSplitThread = () => {
    if (!selectedPost) return;
    const content = selectedPost.content;
    const parts: string[] = [];
    let idx = 0;
    while (idx < content.length) {
      parts.push(content.slice(idx, idx + 2900));
      idx += 2900;
    }
    const updated = {
      ...selectedPost,
      is_thread: true,
      thread_parts: parts,
      thread_count: parts.length,
      content: parts.join('\n\n---\n\n'),
    };
    const newVariants = [...variants];
    newVariants[selectedIdx] = updated;
    setVariants(newVariants);
  };

  const postToVariant = (post: Post, index: number): ContentVariant => ({
    content: post.content,
    char_count: post.content.length,
    hashtags: [],
  });

  const form =
    activeTab === 'konten' ? (
      <ContentForm onSubmit={handleContentSubmit} loading={generating} />
    ) : (
      <PromoForm onSubmit={handlePromoSubmit} loading={generating} />
    );

  const preview = (
    <div className="space-y-4">
      {variants.length > 1 && (
        <div
          className="space-y-2"
          role="listbox"
          aria-label="Pilih variasi konten"
        >
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Pilih Variasi
          </p>
          {variants.map((v, i) => (
            <ContentVariantCard
              key={v.id ?? i}
              variant={postToVariant(v, i)}
              index={i}
              selected={selectedIdx === i}
              onSelect={() => setSelectedIdx(i)}
            />
          ))}
        </div>
      )}

      <ContentPreview
        content={selectedPost?.content ?? ''}
        imageUrl={selectedPost?.image_url}
        onPost={selectedPost ? handlePost : undefined}
        onSaveDraft={selectedPost ? handleSaveDraft : undefined}
        onSplitThread={
          selectedPost && selectedPost.content.length > 3000
            ? handleSplitThread
            : undefined
        }
        loading={posting || savingDraft}
      />
    </div>
  );

  return (
    <DashboardLayout title="Studio">
      <div className="space-y-4">
        {/* Tab switcher */}
        <div className="flex gap-1 rounded-lg border border-gray-200 bg-gray-50 p-1 w-fit">
          {(['konten', 'promo'] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? 'bg-white text-blue-700 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab === 'konten' ? 'Buat Konten' : 'Buat Promosi'}
            </button>
          ))}
        </div>

        {/* Feedback banners */}
        {errorMsg && (
          <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle size={16} className="shrink-0" />
            {errorMsg}
          </div>
        )}
        {successMsg && (
          <div className="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
            <CheckCircle2 size={16} className="shrink-0" />
            {successMsg}
          </div>
        )}

        <BotProgressBar />

        {/* Main layout */}
        <StudioLayout form={form} preview={preview} />
      </div>
    </DashboardLayout>
  );
}
