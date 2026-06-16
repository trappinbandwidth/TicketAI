import { useCallback, useEffect, useMemo, useState, memo } from 'react';
import { Controller, useFormContext } from 'react-hook-form';
import { useDropzone, DropzoneOptions } from 'react-dropzone';
import { getBase64 } from 'src/utils/common-function';
import LucideIcon from 'src/components/lucide-icon';
import { cn } from 'src/lib/utils';

// ----------------------------------------------------------------------

// Constants
const BRAND_PRIMARY = '#1a365d';

// Extended file type with VersionData and preview URL
interface ExtendedFile extends File {
  VersionData?: string;
  preview?: string;
}

// Props type extending DropzoneOptions
type RHFDropzoneProps = Omit<DropzoneOptions, 'onDrop'> & {
  name: string;
  label?: string;
  helperText?: string;
  showFileList?: boolean;
  maxFiles?: number;
  compact?: boolean;
};

// Helper function to format file size
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};

// Helper function to get file icon based on type
const getFileIcon = (type: string): string => {
  if (type.includes('pdf')) return 'FileText';
  if (type.includes('image')) return 'Image';
  if (type.includes('word') || type.includes('doc')) return 'FileText';
  if (type.includes('excel') || type.includes('sheet')) return 'FileSpreadsheet';
  return 'File';
};

// Helper function to get file icon color
const getFileIconColor = (type: string): string => {
  if (type.includes('pdf')) return '#E53935';
  if (type.includes('image')) return '#43A047';
  if (type.includes('word') || type.includes('doc')) return '#1976D2';
  if (type.includes('excel') || type.includes('sheet')) return '#2E7D32';
  return '#757575';
};

// ================== File Item Component ==================
interface FileItemProps {
  file: ExtendedFile;
  index: number;
  onRemove: (index: number) => void;
  disabled?: boolean;
}

const FileItem = memo(({ file, index, onRemove, disabled }: FileItemProps) => {
  const isImage = file.type.includes('image');

  const previewUrl = useMemo(() => {
    if (isImage && file.preview) return file.preview;
    if (isImage) return URL.createObjectURL(file);
    return null;
  }, [file, isImage]);

  return (
    <div className="relative flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3 transition hover:border-[rgba(26,54,93,0.2)] hover:bg-[rgba(26,54,93,0.04)]">
      <div
        className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-xl border"
        style={{
          backgroundColor: `${getFileIconColor(file.type)}14`,
          borderColor: `${getFileIconColor(file.type)}26`,
        }}
      >
        {previewUrl ? (
          <img
            src={previewUrl}
            alt={file.name}
            className="h-full w-full object-cover"
          />
        ) : (
          <LucideIcon
            name={getFileIcon(file.type)}
            size={24}
            color={getFileIconColor(file.type)}
          />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <p className="truncate text-[0.8125rem] font-semibold text-slate-900" title={file.name}>
          {file.name}
        </p>
        <div className="flex items-center gap-2 text-[0.7rem]">
          <span className="text-slate-500">
            {formatFileSize(file.size)}
          </span>
          <span className="h-[3px] w-[3px] rounded-full bg-slate-400" />
          <span
            className="font-medium uppercase"
            style={{ color: getFileIconColor(file.type) }}
          >
            {file.type.split('/')[1]?.substring(0, 4) || 'FILE'}
          </span>
        </div>
      </div>

      <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove(index);
          }}
          disabled={disabled}
          className="rounded-full bg-black/5 p-2 text-slate-500 transition hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label={`Remove ${file.name}`}
        >
          <LucideIcon name="Trash2" size={18} />
      </button>
    </div>
  );
});
FileItem.displayName = 'FileItem';

// ================== Main Component ==================
export default function RHFDropzone({
  name,
  label,
  accept,
  helperText,
  showFileList = true,
  maxFiles,
  compact = false,
  disabled,
  ...other
}: RHFDropzoneProps) {
  const { control, register, unregister, setValue, watch } = useFormContext();
  const files: ExtendedFile[] = watch(name) || [];
  const [isDragging, setIsDragging] = useState(false);

  // Handle file drop
  const onDrop = useCallback(
    (droppedFiles: File[]) => {
      const newFiles = droppedFiles.map((file) => {
        // Create preview URL for images
        const extendedFile = file as ExtendedFile;
        if (file.type.includes('image')) {
          extendedFile.preview = URL.createObjectURL(file);
        }
        // Get base64 for upload
        getBase64(file, (err: any, res: string) => {
          if (res) {
            extendedFile.VersionData = res;
          }
        });
        return extendedFile;
      });

      // Append to existing files or replace based on maxFiles
      const updatedFiles = maxFiles === 1
        ? newFiles
        : [...files, ...newFiles].slice(0, maxFiles || Infinity);

      setValue(name, updatedFiles, { shouldValidate: true });
    },
    [setValue, name, files, maxFiles]
  );

  // Handle file removal
  const handleRemoveFile = useCallback(
    (indexToRemove: number) => {
      const fileToRemove = files[indexToRemove];
      // Revoke object URL to prevent memory leaks
      if (fileToRemove?.preview) {
        URL.revokeObjectURL(fileToRemove.preview);
      }
      const updatedFiles = files.filter((_, index) => index !== indexToRemove);
      setValue(name, updatedFiles, { shouldValidate: true });
    },
    [files, setValue, name]
  );

  // Handle remove all files
  const handleRemoveAll = useCallback(() => {
    // Revoke all object URLs
    files.forEach((file) => {
      if (file.preview) {
        URL.revokeObjectURL(file.preview);
      }
    });
    setValue(name, [], { shouldValidate: true });
  }, [files, setValue, name]);

  const {
    getRootProps,
    getInputProps,
    isFocused,
    isDragAccept,
    isDragReject,
  } = useDropzone({
    onDrop,
    accept,
    disabled,
    maxFiles,
    onDragEnter: () => setIsDragging(true),
    onDragLeave: () => setIsDragging(false),
    ...other,
  });

  // Dynamic dropzone styles
  const dropzoneStyle = useMemo(() => {
    let borderColor = 'rgba(15, 23, 42, 0.12)';
    let bgColor = 'rgba(26, 54, 93, 0.02)';

    if (isDragAccept || isDragging) {
      borderColor = '#22c55e';
      bgColor = 'rgba(34, 197, 94, 0.06)';
    } else if (isDragReject) {
      borderColor = '#E53935';
      bgColor = 'rgba(229, 57, 53, 0.06)';
    } else if (isFocused) {
      borderColor = BRAND_PRIMARY;
      bgColor = 'rgba(26, 54, 93, 0.04)';
    }

    return {
      borderColor,
      bgColor,
    };
  }, [isFocused, isDragAccept, isDragReject, isDragging]);

  // Cleanup on unmount
  useEffect(() => {
    register(name);
    return () => {
      // Revoke all object URLs on unmount
      files.forEach((file) => {
        if (file.preview) {
          URL.revokeObjectURL(file.preview);
        }
      });
      unregister(name);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [register, unregister, name]);

  const hasFiles = files.length > 0;

  return (
    <Controller
      name={name}
      control={control}
      render={({ fieldState: { error } }) => (
        <div>
          {label && (
            <label htmlFor={name} className="mb-1.5 block text-sm font-semibold text-slate-900">
              {label}
            </label>
          )}

          <div
            {...getRootProps()}
            className={cn(
              'rounded-3xl border-2 border-dashed text-center transition-all duration-200',
              compact ? 'p-6' : 'p-6 sm:p-8',
              disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:border-[#1a365d] hover:bg-[rgba(26,54,93,0.04)]',
              error && 'border-red-500'
            )}
            style={{
              borderColor: error ? '#dc2626' : dropzoneStyle.borderColor,
              backgroundColor: dropzoneStyle.bgColor,
            }}
          >
            <input {...getInputProps()} id={name} />

            <div
              className="mx-auto mb-2 flex items-center justify-center rounded-full bg-[rgba(26,54,93,0.08)] transition-transform duration-300"
              style={{
                width: compact ? 48 : 64,
                height: compact ? 48 : 64,
                transform: isDragging ? 'scale(1.1)' : 'scale(1)',
              }}
            >
              <LucideIcon
                name={isDragging ? 'Upload' : 'CloudUpload'}
                size={compact ? 24 : 32}
                color={BRAND_PRIMARY}
              />
            </div>

            <p className={cn('mb-0.5 font-semibold text-[#1a365d]', compact ? 'text-sm' : 'text-base')}>
              {isDragging ? 'Drop files here' : 'Drop files here or click to upload'}
            </p>
            <p className="block text-xs text-slate-500">
              {accept
                ? `Accepted formats: ${Object.keys(accept)
                  .map((key) => key.split('/')[1]?.toUpperCase())
                  .filter(Boolean)
                  .join(', ')}`
                : 'All file types accepted'}
              {maxFiles && ` • Max ${maxFiles} file${maxFiles > 1 ? 's' : ''}`}
            </p>

            {isDragging && (
              <div className="mt-2 overflow-hidden rounded-full bg-[rgba(34,197,94,0.2)]">
                <div className="h-1.5 w-full animate-pulse bg-[#22c55e]" />
              </div>
            )}
          </div>

          {showFileList && hasFiles && (
            <div className="mt-2">
              <div className="mb-1.5 flex items-center justify-between gap-3">
                <p className="text-[0.8125rem] font-semibold text-slate-500">
                  {files.length} file{files.length > 1 ? 's' : ''} selected
                </p>
                {files.length > 1 && (
                  <button
                    type="button"
                    onClick={handleRemoveAll}
                    className="text-xs font-semibold text-[#E53935] transition hover:underline"
                  >
                    Remove all
                  </button>
                )}
              </div>

              <div className="space-y-2">
                {files.map((file, index) => (
                  <FileItem
                    key={`${file.name}-${index}-${file.size}`}
                    file={file}
                    index={index}
                    onRemove={handleRemoveFile}
                    disabled={disabled}
                  />
                ))}
              </div>
            </div>
          )}

          {(error?.message || helperText) && (
            <p className={cn('mt-1.5 text-sm', error ? 'text-red-600' : 'text-slate-500')}>
              {error?.message || helperText}
            </p>
          )}
        </div>
      )}
    />
  );
}
