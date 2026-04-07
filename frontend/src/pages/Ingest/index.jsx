import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
  Form,
  Select,
  Upload,
  Button,
  message,
  List,
  Alert,
  Progress,
  Space,
  Typography,
  Tag,
  Statistic,
  Row,
  Col,
  Divider,
} from 'antd';
import {
  InboxOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { getBooks, uploadBookIndexFile } from '../../api';

const { Dragger } = Upload;
const { Text } = Typography;

/** Above this size we skip full browser parse and rely on server-side parsing */
const PREVIEW_MAX_BYTES = 2 * 1024 * 1024;

const STAGE_WEIGHT = {
  starting: 48,
  embedding_chunks: 58,
  openie: 68,
  embedding_entities: 75,
  embedding_facts: 82,
  graph_construction: 90,
  completed: 100,
};

const Ingest = () => {
  const [form] = Form.useForm();
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewDocs, setPreviewDocs] = useState([]);
  const [previewNote, setPreviewNote] = useState(null);
  const [indexing, setIndexing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [progressData, setProgressData] = useState(null);
  const [uploading, setUploading] = useState(false);
  const eventSourceRef = useRef(null);
  const uploadPhaseRef = useRef(false);

  useEffect(() => {
    fetchBooks();
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const fetchBooks = async () => {
    try {
      setLoading(true);
      const res = await getBooks();
      setBooks(res.data.books || []);
    } catch (err) {
      message.error('获取书籍列表失败');
    } finally {
      setLoading(false);
    }
  };

  const parsePreviewOnly = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target.result;
        const extension = file.name.split('.').pop().toLowerCase();
        try {
          let docs = [];
          if (extension === 'json') {
            const parsed = JSON.parse(content);
            if (Array.isArray(parsed)) {
              docs = parsed.filter((doc) => typeof doc === 'string' && doc.trim());
            } else {
              throw new Error('JSON 文件必须是字符串数组');
            }
          } else {
            let paragraphs = content.split('\n\n');
            if (paragraphs.length === 1) {
              paragraphs = content.split('\n');
            }
            docs = paragraphs.map((p) => p.trim()).filter((p) => p.length > 0);
          }
          resolve(docs);
        } catch (err) {
          reject(err);
        }
      };
      reader.onerror = () => reject(new Error('文件读取失败'));
      reader.readAsText(file);
    });
  };

  const handleUpload = async (info) => {
    const { file } = info;
    const f = file.originFileObj || file;
    if (!f) return;

    setSelectedFile(f);
    setPreviewNote(null);
    setPreviewDocs([]);

    if (f.size > PREVIEW_MAX_BYTES) {
      setPreviewNote(
        `大文件（约 ${(f.size / 1024 / 1024).toFixed(1)} MB）：不在浏览器内全文解析，提交后将通过 multipart 上传并由服务端解析。`
      );
      message.success('已选择文件');
      return;
    }

    try {
      const docs = await parsePreviewOnly(f);
      setPreviewDocs(docs);
      message.success(`本地预览解析成功，约 ${docs.length} 条文档（服务端将以相同规则解析）`);
    } catch (err) {
      message.error(`预览解析失败: ${err.message}`);
      setSelectedFile(null);
    }
  };

  const startProgressTracking = () => {
    const apiBaseUrl = process.env.REACT_APP_API_URL || '/api';
    const eventSource = new EventSource(`${apiBaseUrl}/index/progress`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setProgressData(data);

        if (uploadPhaseRef.current) {
          setProgressData(data);
          return;
        }

        if (data.status === 'failed') {
          eventSource.close();
          setIndexing(false);
          setProgress(0);
          message.error(`索引失败: ${data.progress?.error || data.message}`);
          return;
        }

        if (data.done || data.status === 'completed') {
          eventSource.close();
          setIndexing(false);
          setProgress(100);
          setResult({
            status: 'completed',
            message: data.message,
            num_docs: data.progress?.total_docs || 0,
          });
          message.success('索引完成');
          return;
        }

        const { current_stage } = data.progress || {};
        const pct = STAGE_WEIGHT[current_stage] ?? 55;
        setProgress(Math.min(99, pct));
      } catch (err) {
        console.error('SSE parse error:', err);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      if (!uploadPhaseRef.current) {
        setIndexing(false);
      }
    };
  };

  const resetForm = () => {
    form.resetFields();
    setSelectedFile(null);
    setPreviewDocs([]);
    setPreviewNote(null);
    setResult(null);
    setProgress(0);
    setProgressData(null);
    setUploading(false);
  };

  const handleIndex = async (values) => {
    if (!selectedFile) {
      message.warning('请先上传文件');
      return;
    }

    try {
      setIndexing(true);
      setUploading(true);
      setProgress(0);
      setResult(null);
      setProgressData(null);
      uploadPhaseRef.current = true;
      startProgressTracking();

      const res = await uploadBookIndexFile(
        values.book_id,
        selectedFile,
        (progressEvent) => {
          if (progressEvent.total) {
            const pct = Math.round((progressEvent.loaded / progressEvent.total) * 42);
            setProgress(pct);
          }
        }
      );

      uploadPhaseRef.current = false;
      setUploading(false);

      if (res.data.status === 'accepted') {
        message.info('上传完成，索引任务已启动…');
      } else {
        setProgress(100);
        setResult(res.data);
        setIndexing(false);
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
        }
      }
    } catch (err) {
      uploadPhaseRef.current = false;
      setUploading(false);
      message.error(err.response?.data?.detail || '上传或索引失败');
      setProgress(0);
      setIndexing(false);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    }
  };

  const getStageText = (stage) => {
    const stageMap = {
      starting: '初始化中',
      embedding_chunks: '正在生成文档嵌入向量',
      openie: '正在提取实体和关系',
      embedding_entities: '正在生成实体嵌入向量',
      embedding_facts: '正在生成事实嵌入向量',
      graph_construction: '正在构建知识图谱',
      completed: '完成',
      failed: '失败',
    };
    return stageMap[stage] || stage;
  };

  const getStageColor = (stage) => {
    const colorMap = {
      starting: 'blue',
      embedding_chunks: 'cyan',
      openie: 'purple',
      embedding_entities: 'magenta',
      embedding_facts: 'volcano',
      graph_construction: 'orange',
      completed: 'green',
      failed: 'red',
    };
    return colorMap[stage] || 'default';
  };

  const uploadProps = {
    name: 'file',
    accept: '.txt,.md,.json,.jsonl',
    showUploadList: false,
    beforeUpload: () => false,
    onChange: handleUpload,
  };

  return (
    <div>
      <Form form={form} layout="vertical" onFinish={handleIndex}>
        <Form.Item
          name="book_id"
          label="目标书籍"
          rules={[{ required: true, message: '请选择目标书籍' }]}
        >
          <Select
            placeholder="选择要索引到的书籍"
            loading={loading}
            showSearch
            optionFilterProp="children"
          >
            {books.map((book) => (
              <Select.Option key={book.book_id} value={book.book_id}>
                {book.book_id} ({book.doc_count || 0} 篇文档)
              </Select.Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item label="上传文件">
          <Dragger {...uploadProps}>
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域</p>
            <p className="ant-upload-hint">
              支持 .txt、.md（每行/段一个文档）和 .json、.jsonl。大文件将使用 multipart 上传，无需在浏览器打包整包 JSON。
            </p>
          </Dragger>
        </Form.Item>

        {previewNote && (
          <Alert type="info" message={previewNote} style={{ marginBottom: 16 }} showIcon />
        )}

        {previewDocs.length > 0 && (
          <Card
            title={`文档预览 (约 ${previewDocs.length} 条，≤2MB 文件)`}
            size="small"
            style={{ marginBottom: 24 }}
          >
            <List
              dataSource={previewDocs.slice(0, 5)}
              renderItem={(item, index) => (
                <List.Item>
                  <Text ellipsis style={{ width: '100%' }}>
                    {index + 1}. {item.substring(0, 200)}
                    {item.length > 200 ? '...' : ''}
                  </Text>
                </List.Item>
              )}
            />
            {previewDocs.length > 5 && (
              <Text type="secondary">... 还有 {previewDocs.length - 5} 条文档</Text>
            )}
          </Card>
        )}

        {indexing && progressData && !uploading && (
          <Card size="small" style={{ marginBottom: 24 }}>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic
                  title="状态"
                  value={progressData.status === 'indexing' ? '索引中' : progressData.status}
                  prefix={
                    progressData.status === 'indexing' ? <SyncOutlined spin /> : <CheckCircleOutlined />
                  }
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="当前阶段"
                  value={getStageText(progressData.progress?.current_stage)}
                  valueStyle={{ fontSize: 16 }}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="进度"
                  value={progressData.progress?.processed_docs || 0}
                  suffix={`/ ${progressData.progress?.total_docs || 0}`}
                />
              </Col>
            </Row>
            <Divider style={{ margin: '16px 0' }} />
            <Progress
              percent={progress}
              status={progressData.status === 'failed' ? 'exception' : 'active'}
              strokeColor={{
                '0%': '#108ee9',
                '100%': '#87d068',
              }}
            />
            {progressData.progress?.current_stage && (
              <div style={{ marginTop: 8 }}>
                <Tag color={getStageColor(progressData.progress.current_stage)}>
                  {getStageText(progressData.progress.current_stage)}
                </Tag>
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  {progressData.message}
                </Text>
              </div>
            )}
          </Card>
        )}

        {indexing && (!progressData || uploading) && (
          <div style={{ marginBottom: 24 }}>
            <Progress percent={progress} status="active" />
            <Text>{uploading ? '正在上传文件到服务器（multipart）…' : '正在连接进度…'}</Text>
          </div>
        )}

        {result && !indexing && (
          <Alert
            message="索引完成"
            description={
              <div>
                <p>状态: {result.status}</p>
                <p>文档数量: {result.num_docs}</p>
                <p>Book ID: {result.book_id || form.getFieldValue('book_id')}</p>
              </div>
            }
            type="success"
            showIcon
            icon={<CheckCircleOutlined />}
            style={{ marginBottom: 24 }}
          />
        )}

        <Form.Item>
          <Space>
            <Button
              type="primary"
              htmlType="submit"
              icon={<PlayCircleOutlined />}
              loading={indexing}
              disabled={!selectedFile || indexing}
            >
              开始索引
            </Button>
            <Button onClick={resetForm} disabled={indexing}>
              重置
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
};

export default Ingest;
