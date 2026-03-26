import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Select,
  Input,
  Button,
  message,
  List,
  Typography,
  Space,
  Tag,
  Divider,
  Spin,
  Empty,
} from 'antd';
import {
  SearchOutlined,
  BookOutlined,
  TeamOutlined,
  ClearOutlined,
} from '@ant-design/icons';
import { getBooks, getBusinesses, retrieveByBusiness, qaByBusiness } from '../../api';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

const Query = () => {
  const [form] = Form.useForm();
  const [books, setBooks] = useState([]);
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [queryMode, setQueryMode] = useState('qa'); // 'qa' or 'retrieve'
  const [results, setResults] = useState([]);
  const [searchedBooks, setSearchedBooks] = useState([]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [booksRes, businessesRes] = await Promise.all([
        getBooks(),
        getBusinesses(),
      ]);
      setBooks(booksRes.data.books || []);
      setBusinesses(businessesRes.data.businesses || []);
    } catch (err) {
      message.error('加载数据失败');
    }
  };

  const handleQuery = async (values) => {
    if (!values.queries?.trim()) {
      message.warning('请输入查询内容');
      return;
    }

    try {
      setLoading(true);
      setResults([]);
      setSearchedBooks([]);

      const queries = values.queries.split('\n').filter(q => q.trim());
      const params = {
        business_id: values.business_id,
        queries,
        num_to_retrieve: values.num_to_retrieve || 10,
        return_scores: true,
      };

      let res;
      if (queryMode === 'qa') {
        res = await qaByBusiness(params);
      } else {
        res = await retrieveByBusiness(params);
      }

      setResults(res.data.results || []);
      setSearchedBooks(res.data.books_searched || []);
      message.success(`查询完成，搜索了 ${res.data.books_searched?.length || 0} 本书`);
    } catch (err) {
      message.error(err.response?.data?.detail || '查询失败');
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    form.resetFields();
    setResults([]);
    setSearchedBooks([]);
  };

  return (
    <div>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleQuery}
        initialValues={{ num_to_retrieve: 10 }}
      >
        <Form.Item
          name="business_id"
          label="选择业务"
          rules={[{ required: true, message: '请选择业务' }]}
        >
          <Select
            placeholder="选择要查询的业务"
            showSearch
            optionFilterProp="children"
          >
            {businesses.map(b => (
              <Select.Option key={b.business_id} value={b.business_id}>
                <TeamOutlined style={{ marginRight: 8 }} />
                {b.name || b.business_id}
                <Tag color="blue" style={{ marginLeft: 8 }}>{b.book_count || 0} 本书</Tag>
              </Select.Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item label="查询模式">
          <Space>
            <Button
              type={queryMode === 'qa' ? 'primary' : 'default'}
              onClick={() => setQueryMode('qa')}
            >
              问答模式
            </Button>
            <Button
              type={queryMode === 'retrieve' ? 'primary' : 'default'}
              onClick={() => setQueryMode('retrieve')}
            >
              检索模式
            </Button>
          </Space>
          <div style={{ marginTop: 8, color: '#666' }}>
            {queryMode === 'qa'
              ? '问答模式：使用 LLM 基于检索结果生成答案'
              : '检索模式：仅返回相关文档片段'}
          </div>
        </Form.Item>

        <Form.Item
          name="queries"
          label="查询内容"
          rules={[{ required: true, message: '请输入查询内容' }]}
        >
          <TextArea
            rows={4}
            placeholder="输入查询内容，每行一个问题&#10;例如：&#10;方源穿的是什么颜色的袍子？&#10;方源被困了多长时间？"
          />
        </Form.Item>

        <Form.Item
          name="num_to_retrieve"
          label="检索数量"
        >
          <Select style={{ width: 120 }}>
            <Select.Option value={5}>5 条</Select.Option>
            <Select.Option value={10}>10 条</Select.Option>
            <Select.Option value={20}>20 条</Select.Option>
            <Select.Option value={50}>50 条</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item>
          <Space>
            <Button
              type="primary"
              htmlType="submit"
              icon={<SearchOutlined />}
              loading={loading}
            >
              查询
            </Button>
            <Button
              icon={<ClearOutlined />}
              onClick={handleClear}
            >
              清空
            </Button>
          </Space>
        </Form.Item>
      </Form>

      {searchedBooks.length > 0 && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space>
            <Text type="secondary">搜索的书籍：</Text>
            {searchedBooks.map(bookId => (
              <Tag key={bookId} icon={<BookOutlined />} color="blue">
                {bookId}
              </Tag>
            ))}
          </Space>
        </Card>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>正在查询...</div>
        </div>
      )}

      {!loading && results.length > 0 && (
        <List
          dataSource={results}
          renderItem={(item, index) => (
            <Card
              key={index}
              style={{ marginBottom: 16 }}
              title={
                <Space>
                  <Tag color="blue">Q{index + 1}</Tag>
                  <Text strong>{item.query}</Text>
                </Space>
              }
            >
              {queryMode === 'qa' && item.answer && (
                <>
                  <div style={{ marginBottom: 16 }}>
                    <Text type="secondary">答案：</Text>
                    <Paragraph
                      style={{ marginTop: 8, marginBottom: 0 }}
                      copyable
                    >
                      {item.answer}
                    </Paragraph>
                  </div>
                  <Divider style={{ margin: '12px 0' }} />
                </>
              )}

              <Text type="secondary">相关文档：</Text>
              <List
                dataSource={item.passages || []}
                style={{ marginTop: 8 }}
                renderItem={(passage, pIndex) => (
                  <List.Item style={{ padding: '8px 0', borderBottom: pIndex < item.passages.length - 1 ? '1px solid #f0f0f0' : 'none' }}>
                    <div style={{ width: '100%' }}>
                      <Space>
                        <Tag>{pIndex + 1}</Tag>
                        {passage.book_id && (
                          <Tag color="blue" icon={<BookOutlined />}>
                            {passage.book_id}
                          </Tag>
                        )}
                      </Space>
                      <Paragraph
                        ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                        style={{ marginBottom: 0, marginTop: 8 }}
                      >
                        {passage.content}
                      </Paragraph>
                    </div>
                  </List.Item>
                )}
              />
            </Card>
          )}
        />
      )}

      {!loading && results.length === 0 && form.getFieldValue('queries') === undefined && (
        <Empty
          description="输入查询内容开始搜索"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      )}
    </div>
  );
};

export default Query;
