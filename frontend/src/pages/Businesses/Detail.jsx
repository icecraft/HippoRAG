import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Descriptions,
  Table,
  Button,
  Transfer,
  message,
  Spin,
  Space,
  Tag,
  Divider,
} from 'antd';
import { ArrowLeftOutlined, SaveOutlined } from '@ant-design/icons';
import { getBusiness, getBusinessBooks, getBooks, bindBooks, unbindBooks } from '../../api';

const BusinessDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [business, setBusiness] = useState(null);
  const [boundBooks, setBoundBooks] = useState([]);
  const [allBooks, setAllBooks] = useState([]);
  const [selectedKeys, setSelectedKeys] = useState([]);
  const [saving, setSaving] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [businessRes, boundRes, booksRes] = await Promise.all([
        getBusiness(id),
        getBusinessBooks(id),
        getBooks(),
      ]);
      setBusiness(businessRes.data);
      setBoundBooks(boundRes.data.books?.map(b => b.book_id) || []);
      setAllBooks(booksRes.data.books || []);
      setSelectedKeys(boundRes.data.books?.map(b => b.book_id) || []);
    } catch (err) {
      message.error('获取数据失败');
      console.error(err);
      navigate('/businesses');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [id]);

  const handleSave = async () => {
    try {
      setSaving(true);

      // Find books to bind and unbind
      const toBind = selectedKeys.filter(k => !boundBooks.includes(k));
      const toUnbind = boundBooks.filter(k => !selectedKeys.includes(k));

      if (toBind.length > 0) {
        await bindBooks(id, toBind);
      }
      if (toUnbind.length > 0) {
        await unbindBooks(id, toUnbind);
      }

      message.success('保存成功');
      fetchData();
    } catch (err) {
      message.error(err.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Spin size="large" />
      </div>
    );
  }

  const transferDataSource = allBooks.map(book => ({
    key: book.book_id,
    title: book.book_id,
    description: `${book.doc_count || 0} 篇文档`,
  }));

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/businesses')}>
          返回列表
        </Button>
      </div>

      <Card title="业务信息" style={{ marginBottom: 24 }}>
        <Descriptions>
          <Descriptions.Item label="Business ID">{business?.business_id}</Descriptions.Item>
          <Descriptions.Item label="名称">{business?.name}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={business?.status === 'active' ? 'green' : 'default'}>
              {business?.status === 'active' ? '活跃' : '禁用'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="描述" span={3}>
            {business?.description || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {business?.created_at ? new Date(business.created_at).toLocaleString('zh-CN') : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card
        title="绑定书籍"
        extra={
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={saving}
          >
            保存更改
          </Button>
        }
      >
        <Transfer
          dataSource={transferDataSource}
          titles={['可用书籍', '已绑定书籍']}
          targetKeys={selectedKeys}
          onChange={setSelectedKeys}
          render={item => item.title}
          listStyle={{ width: 300, height: 400 }}
          showSearch
          filterOption={(input, option) =>
            option.title.toLowerCase().includes(input.toLowerCase())
          }
        />
      </Card>
    </div>
  );
};

export default BusinessDetail;
