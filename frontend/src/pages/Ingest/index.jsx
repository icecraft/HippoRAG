import React, { useState, useEffect } from 'react';
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
} from 'antd';
import {
  UploadOutlined,
  FileTextOutlined,
  InboxOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import { getBooks, indexDocuments } from '../../api';

const { Dragger } = Upload;
const { TextArea } = Input;
const { Text } = Typography;

const Ingest = () => {
  const [form] = Form.useForm();
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fileContent, setFileContent] = useState(null);
  const [parsedDocs, setParsedDocs] = useState([]);
  const [indexing, setIndexing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetchBooks();
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
            // Parse as text file (one document per line)
            docs = content
              .split('\n')
              .map(line => line.trim())
              .filter(line => line.length > 0);
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

  const handleIndex = async (values) => {
    if (!parsedDocs.length) {
      message.warning('请先上传文件');
      return;
    }

    try {
      setIndexing(true);
      setProgress(0);
      setResult(null);

      // Simulate progress
      const progressInterval = setInterval(() => {
        setProgress(prev => Math.min(prev + 10, 90));
      }, 500);

      const res = await indexDocuments(values.book_id, parsedDocs);

      clearInterval(progressInterval);
      setProgress(100);

      setResult(res.data);
      message.success(`索引完成，共 ${res.data.num_docs} 条文档`);
    } catch (err) {
      message.error(err.response?.data?.detail || '索引失败');
      setProgress(0);
    } finally {
      setIndexing(false);
    }
  };

  const uploadProps = {
    name: 'file',
    accept: '.txt,.json',
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
              支持 .txt（每行一个文档）和 .json（字符串数组）格式
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

        {indexing && (
          <div style={{ marginBottom: 24 }}>
            <Progress percent={progress} status="active" />
            <Text>正在索引文档，请稍候...</Text>
          </div>
        )}

        {result && (
          <Alert
            message="索引完成"
            description={
              <div>
                <p>状态: {result.status}</p>
                <p>文档数量: {result.num_docs}</p>
                <p>Book ID: {result.book_id}</p>
              </div>
            }
            type="success"
            showIcon
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
              disabled={!parsedDocs.length}
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
              }}
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
