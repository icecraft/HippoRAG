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
  Input,
  Divider,
  Typography,
  Tag,
  Statistic,
  Row,
  Col,
} from 'antd';
import {
  UploadOutlined,
  FileTextOutlined,
  InboxOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { getBooks, indexDocumentsAsync, uploadFile } from '../../api';

const { Dragger } = Upload;
const { TextArea } = Input;
const { Text, Title } = Typography;

const Ingest = () => {
  const [form] = Form.useForm();
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fileContent, setFileContent] = useState(null);
  const [parsedDocs, setParsedDocs] = useState([]);
  const [indexing, setIndexing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [progressData, setProgressData] = useState(null);
  const eventSourceRef = useRef(null);

  useEffect(() => {
    fetchBooks();
    return () => {
      // Cleanup SSE connection on unmount
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

  const parseFile = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target.result;
        setFileContent(content);

        // Determine file type and parse
        const extension = file.name.split('.').pop().toLowerCase();

        try {
          let docs = [];

          if (extension === 'json') {
            // Parse JSON array
            const parsed = JSON.parse(content);
            if (Array.isArray(parsed)) {
              docs = parsed.filter(doc => typeof doc === 'string' && doc.trim());
            } else {
              throw new Error('JSON 文件必须是字符串数组');
            }
          } else {
            // Parse as text file (one document per line or paragraph)
            // Split by double newlines first (paragraphs), then by single if too long
            let paragraphs = content.split('\n\n');
            if (paragraphs.length === 1) {
              paragraphs = content.split('\n');
            }
            docs = paragraphs
              .map(p => p.trim())
              .filter(p => p.length > 0);
          }

          setParsedDocs(docs);
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
    if (file.status === 'done' || file) {
      try {
        await parseFile(file.originFileObj || file);
        message.success(`文件解析成功，共 ${parsedDocs.length} 条文档`);
      } catch (err) {
        message.error(`解析失败: ${err.message}`);
        setParsedDocs([]);
      }
    }
  };

  // SSE progress tracking
  const startProgressTracking = () => {
    const apiBaseUrl = process.env.REACT_APP_API_URL || '/api';
    const eventSource = new EventSource(`${apiBaseUrl}/index/progress`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setProgressData(data);

        // Calculate progress percentage
        if (data.progress) {
          const { total_docs, processed_docs, current_stage } = data.progress;
          if (total_docs > 0) {
            const percentage = Math.round((processed_docs / total_docs) * 100);
            setProgress(percentage);
          }
        }

        // Handle completion
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
        }

        // Handle failure
        if (data.status === 'failed') {
          eventSource.close();
          setIndexing(false);
          setProgress(0);
          message.error(`索引失败: ${data.progress?.error || data.message}`);
        }
      } catch (err) {
        console.error('SSE parse error:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE error:', err);
      eventSource.close();
      setIndexing(false);
    };
  };

  const handleIndex = async (values) => {
    if (!parsedDocs.length) {
      message.warning('请先上传文件');
      return;
    }

    try {
      setIndexing(true);
      setProgress(0);
      setResult(null);
      setProgressData(null);

      // Start SSE progress tracking first
      startProgressTracking();

      // Start async indexing
      const res = await indexDocumentsAsync(values.book_id, parsedDocs);

      if (res.data.status === 'accepted') {
        message.info('索引任务已启动，请等待完成...');
      } else {
        // If completed synchronously (shouldn't happen with async endpoint)
        setProgress(100);
        setResult(res.data);
        setIndexing(false);
      }
    } catch (err) {
      message.error(err.response?.data?.detail || '索引失败');
      setProgress(0);
      setIndexing(false);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    }
  };

  // Handle file upload via API
  const handleFileUpload = async (values) => {
    if (!fileContent) {
      message.warning('请先上传文件');
      return;
    }

    try {
      setIndexing(true);
      setProgress(0);
      setResult(null);
      setProgressData(null);

      // Start SSE progress tracking first
      startProgressTracking();

      // Create file object from parsed content
      const file = new File([fileContent], 'document.txt', { type: 'text/plain' });

      const res = await uploadFile(file, (progressEvent) => {
        // Upload progress (not indexing progress)
        const uploadPercent = Math.round((progressEvent.loaded / progressEvent.total) * 20);
        setProgress(uploadPercent);
      });

      if (res.data.status === 'accepted') {
        message.info('文件上传成功，索引任务已启动...');
      }
    } catch (err) {
      message.error(err.response?.data?.detail || '上传失败');
      setProgress(0);
      setIndexing(false);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    }
  };

  const getStageText = (stage) => {
    const stageMap = {
      'starting': '初始化中',
      'embedding_chunks': '正在生成文档嵌入向量',
      'openie': '正在提取实体和关系',
      'embedding_entities': '正在生成实体嵌入向量',
      'embedding_facts': '正在生成事实嵌入向量',
      'graph_construction': '正在构建知识图谱',
      'completed': '完成',
      'failed': '失败',
    };
    return stageMap[stage] || stage;
  };

  const getStageColor = (stage) => {
    const colorMap = {
      'starting': 'blue',
      'embedding_chunks': 'cyan',
      'openie': 'purple',
      'embedding_entities': 'magenta',
      'embedding_facts': 'volcano',
      'graph_construction': 'orange',
      'completed': 'green',
      'failed': 'red',
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
            {books.map(book => (
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
              支持 .txt、.md（每行/段一个文档）和 .json、.jsonl（字符串数组）格式
            </p>
          </Dragger>
        </Form.Item>

        {parsedDocs.length > 0 && (
          <Card
            title={`文档预览 (共 ${parsedDocs.length} 条)`}
            size="small"
            style={{ marginBottom: 24 }}
          >
            <List
              dataSource={parsedDocs.slice(0, 5)}
              renderItem={(item, index) => (
                <List.Item>
                  <Text ellipsis style={{ width: '100%' }}>
                    {index + 1}. {item.substring(0, 200)}{item.length > 200 ? '...' : ''}
                  </Text>
                </List.Item>
              )}
            />
            {parsedDocs.length > 5 && (
              <Text type="secondary">... 还有 {parsedDocs.length - 5} 条文档</Text>
            )}
          </Card>
        )}

        {indexing && progressData && (
          <Card size="small" style={{ marginBottom: 24 }}>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic
                  title="状态"
                  value={progressData.status === 'indexing' ? '索引中' : progressData.status}
                  prefix={progressData.status === 'indexing' ? <SyncOutlined spin /> : <CheckCircleOutlined />}
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

        {indexing && !progressData && (
          <div style={{ marginBottom: 24 }}>
            <Progress percent={progress} status="active" />
            <Text>正在启动索引任务...</Text>
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
              disabled={!parsedDocs.length || indexing}
            >
              开始索引
            </Button>
            <Button
              onClick={() => {
                form.resetFields();
                setParsedDocs([]);
                setFileContent(null);
                setResult(null);
                setProgress(0);
                setProgressData(null);
              }}
              disabled={indexing}
            >
              重置
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
};

export default Ingest;
