import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const Reviews = () => {
  const [reviews, setReviews] = useState([]);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [averageRating, setAverageRating] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchReviews = async () => {
    try {
      const response = await axios.get('https://smart-health-tst.up.railway.app/api/reviews', {
        params: { productId: '1' }
      });
      setReviews(response.data);
      calculateAverageRating(response.data);
    } catch (error) {
      console.error('Error fetching reviews:', error);
    }
  };

  const calculateAverageRating = (reviewData) => {
    if (reviewData.length === 0) return;
    const avg = reviewData.reduce((acc, review) => acc + review.rating, 0) / reviewData.length;
    setAverageRating(parseFloat(avg.toFixed(1)));
  };

  useEffect(() => {
    fetchReviews();
  }, []);

  const handleSubmit = async () => {
    if (!rating || !comment) {
      alert('Rating dan komentar wajib diisi');
      return;
    }

    setIsSubmitting(true);
    try {
      await axios.post('https://smart-health-tst.up.railway.app/api/reviews', {
        productId: '1',
        userId: 'user123',
        rating,
        comment
      });

      setRating(0);
      setComment('');
      fetchReviews();
      alert('Review berhasil dikirim');
    } catch (error) {
      console.error('Error submitting review:', error);
      alert('Gagal mengirim review');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Reviews Summary Card */}
      <div className="lg:col-span-1">
        <Card>
          <CardHeader>
            <CardTitle>Reviews Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="text-center">
                <div className="text-4xl font-bold text-emerald-500">{averageRating}</div>
                <div className="text-sm text-gray-600">Average Rating</div>
              </div>
              
              <div className="text-center pt-4 border-t">
                <div className="text-2xl font-bold text-gray-700">{reviews.length}</div>
                <div className="text-sm text-gray-600">Total Reviews</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Reviews Content */}
      <div className="lg:col-span-2">
        {/* Write Review Form */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Write a Review</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="block text-gray-700 font-medium mb-2">Rating</label>
                <input
                  type="number"
                  value={rating}
                  onChange={(e) => setRating(Number(e.target.value))}
                  max={5}
                  min={1}
                  className="w-full p-2 border rounded focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-2">Your Review</label>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows="4"
                  className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-emerald-500"
                  placeholder="Share your thoughts about our service..."
                />
              </div>

              <button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="w-full bg-emerald-500 text-white py-2 px-4 rounded-lg hover:bg-emerald-600 transition-all flex items-center justify-center disabled:opacity-50"
              >
                {isSubmitting ? (
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
                ) : (
                  'Submit Review'
                )}
              </button>
            </div>
          </CardContent>
        </Card>

        {/* Reviews List */}
        <Card>
          <CardHeader>
            <CardTitle>Customer Reviews</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y">
              {reviews.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  No reviews yet. Be the first to share your experience!
                </div>
              ) : (
                reviews.map((review) => (
                  <div key={review.id} className="py-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-yellow-400 text-xl">
                        {'★'.repeat(review.rating)}{'☆'.repeat(5 - review.rating)}
                      </div>
                      <span className="text-sm text-gray-600">
                        {new Date(review.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <p className="text-gray-700">{review.comment}</p>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Reviews;