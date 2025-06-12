import React, { useState, useRef, useEffect } from 'react';
import './Home.css';
import axios from 'axios';
import Select from 'react-select'; // Import react-select

function Home() {
    const [selectedFileType, setSelectedFileType] = useState('');
    const [selectedFileName, setSelectedFileName] = useState('No file chosen');
    const [downloadLink, setDownloadLink] = useState('');
    const [columnNames, setColumnNames] = useState([]);
    const [selectedColumns, setSelectedColumns] = useState([]);
    const fileInputRef = useRef(null);
    const videoRef = useRef(null);

    useEffect(() => {
        const video = videoRef.current;
        if (video) {
            video.muted = true;
            video.loop = true;

            const playPromise = video.play();
            if (playPromise !== undefined) {
                playPromise.catch((error) => {
                    console.log("Autoplay prevented");
                });
            }
        }
    }, []);

    const handleButtonClick = () => {
        if (fileInputRef.current) {
            fileInputRef.current.click();
        }
    };

    const handleFileSelect = (event) => {
        const file = event.target.files[0];
        if (file) {
            setSelectedFileName(file.name);
            if (selectedFileType === 'csv') {
                // Read the CSV file to extract column names
                const reader = new FileReader();
                reader.onload = () => {
                    const text = reader.result;
                    const lines = text.split("\n");
                    const headers = lines[0].split(",");
                    setColumnNames(headers);
                };
                reader.readAsText(file);
            }
        } else {
            setSelectedFileName('No file chosen');
        }
    };

    const handleFileTypeChange = (event) => {
        setSelectedFileType(event.target.value);
        setSelectedFileName('No file chosen');
        setDownloadLink('');
        setColumnNames([]);
        setSelectedColumns([]);
    };

    const handleColumnSelection = (selectedOptions) => {
        setSelectedColumns(selectedOptions ? selectedOptions.map(option => option.value) : []);
    };

    const handleSubmit = async () => {
        if (!selectedFileName || selectedFileName === 'No file chosen') {
            alert('Please select a file to proceed.');
            return;
        }

        if (selectedFileType === 'csv' && selectedColumns.length === 0) {
            alert('Please select at least one column.');
            return;
        }

        const file = fileInputRef.current.files[0];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('columns', selectedColumns.join(',')); // Send selected columns

        const endpointMap = {
            pdf: '/redact_pdf',     // Endpoint for PDFs
            csv: '/generate_synthetic', // Endpoint for CSVs
        };

        const endpoint = endpointMap[selectedFileType];
        if (!endpoint) {
            alert('Invalid file type selected.');
            return;
        }

        try {
            const response = await axios.post(`http://localhost:5000${endpoint}`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data', // For file upload
                },
            });

            if (response.status === 200) {
                const blob = new Blob([response.data], { type: response.headers['content-type'] });
                const url = window.URL.createObjectURL(blob);
                setDownloadLink(url);
            } else {
                alert('Error processing file. Please try again.');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred while submitting the file.');
        }
    };

    return (
        <div className="home-container">
            <div className="home-content">
                <video ref={videoRef} className="background-video" src="/bg.mp4" muted loop autoPlay />
                <h1 className="title">Welcome to ObscurifyIT</h1>
                <p className="description">Securely handle and obscure sensitive information from images, PDFs, and CSVs.</p>

                <div className="dropdown-container">
                    <label htmlFor="fileType" className="label">Select File Type to Obscure</label>
                    <select
                        id="fileType"
                        className="dropdown"
                        value={selectedFileType}
                        onChange={handleFileTypeChange}
                    >
                        <option value="" disabled>Select File Type</option>
                        <option value="pdf">PDF</option>
                        <option value="csv">CSV</option>
                    </select>
                </div>

                {selectedFileType && (
                    <div className="upload-container">
                        <label htmlFor="fileInput" className="label">Upload {selectedFileType.toUpperCase()} File:</label>
                        <button className="upload-button" onClick={handleButtonClick}>Choose File</button>
                        <input
                            type="file"
                            className="file-input"
                            style={{ display: 'none' }}
                            onChange={handleFileSelect}
                            ref={fileInputRef}
                        />
                        <span className="file-name">{selectedFileName}</span>
                    </div>
                )}

                {selectedFileType === 'csv' && columnNames.length > 0 && (
                    <div className="dropdown-container">
                        <label htmlFor="columnsSelect" className="label">Select Columns to Redact</label>
                        <Select
                            isMulti
                            name="columnsSelect"
                            options={columnNames.map((column) => ({ label: column, value: column }))}
                            value={selectedColumns.map((col) => ({ label: col, value: col }))}
                            onChange={handleColumnSelection}
                            className="react-select-container"
                            classNamePrefix="react-select"
                            placeholder="Select columns to redact"
                        />
                    </div>
                )}

                {selectedFileType && (
                    <div className="submit-container">
                        <button className="submit-button" onClick={handleSubmit}>Submit</button>
                    </div>
                )}

                {downloadLink && (
                    <div className="download-container">
                        <p className="success-message">
                            File processed successfully! Click the link below to download your redacted file:
                        </p>
                        <a href={downloadLink} className="download-link" download>
                            Download Redacted File
                        </a>
                    </div>
                )}
            </div>
        </div>
    );
}

export default Home;
