import React from 'react';
import { useDropzone } from 'react-dropzone';

function FileDropZone({ files, onDrop, onRemove }) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  return (
    <div className={`dropzone ${isDragActive ? 'active' : ''}`} {...getRootProps()}>
      <input {...getInputProps()} />
      <p className="eyebrow">Files</p>
      <h4>Drag & drop evidence</h4>
      <p className="muted">PDFs, images, transcripts, and more.</p>
      {files.length > 0 && (
        <ul className="file-list">
          {files.map((file) => (
            <li key={file.name}>
              <span>{file.name}</span>
              <button className="chip" type="button" onClick={() => onRemove(file.name)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default FileDropZone;
