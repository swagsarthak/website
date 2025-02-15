import os
import sqlite3
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances
from sklearn.preprocessing import MinMaxScaler
from github import Github

class RepositoryRecommender:
    def __init__(self, database_path: str = 'github_repos.sqlite'):
        """
        Initialize Repository Recommender
        
        :param database_path: Path to SQLite database with repositories
        """
        self.database_path = database_path
        self.scaler = MinMaxScaler()
    
    def _preprocess_repositories(self, repos_df: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess repository data for recommendation
        
        :param repos_df: DataFrame of repositories
        :return: Preprocessed DataFrame
        """
        # Fill missing values
        repos_df['description'] = repos_df['description'].fillna('')
        repos_df['topics'] = repos_df['topics'].fillna('')
        
        # Create combined text feature
        repos_df['combined_text'] = (
            repos_df['full_name'] + ' ' + 
            repos_df['description'] + ' ' + 
            repos_df['language'] + ' ' + 
            repos_df['topics']
        )
        
        # Calculate repository age
        repos_df['created_at'] = pd.to_datetime(repos_df['created_at'])
        repos_df['repo_age'] = (pd.Timestamp.now() - repos_df['created_at']).dt.days
        
        return repos_df
    
    def _create_feature_matrix(self, repos_df: pd.DataFrame) -> np.ndarray:
        """
        Create feature matrix for repositories
        
        :param repos_df: Preprocessed repository DataFrame
        :return: Combined feature matrix
        """
        # TF-IDF Vectorization for text
        text_vectorizer = TfidfVectorizer(stop_words='english', max_features=100)
        text_features = text_vectorizer.fit_transform(repos_df['combined_text'])
        
        # Numerical feature scaling
        numerical_features = self.scaler.fit_transform(
            repos_df[['stars', 'repo_age']].fillna(0)
        )
        
        # Combine text and numerical features
        combined_features = np.hstack([text_features.toarray(), numerical_features])
        
        return combined_features
    
    def generate_recommendations(
        self, 
        github_client, 
        top_n: int = 10, 
        similarity_method: str = 'cosine'
    ) -> pd.DataFrame:
        """
        Generate repository recommendations
        
        :param github_client: Authenticated PyGithub client
        :param top_n: Number of recommendations to return
        :param similarity_method: Similarity calculation method
        :return: DataFrame of recommended repositories
        """
        # Get current user
        user = github_client.get_user()
        username = user.login
        
        # Connect to database
        with sqlite3.connect(self.database_path) as conn:
            # Fetch user's repositories
            user_repos_df = pd.read_sql_query(
                "SELECT * FROM user_repositories WHERE username = ?", 
                conn, 
                params=(username,)
            )
            
            # Fetch all repositories (excluding user's repositories)
            all_repos_query = """
            SELECT * FROM user_repositories 
            WHERE username != ? AND full_name NOT IN (
                SELECT full_name FROM user_repositories WHERE username = ?
            )
            """
            all_repos_df = pd.read_sql_query(
                all_repos_query, 
                conn, 
                params=(username, username)
            )
        
        # Preprocess repositories
        user_repos_df = self._preprocess_repositories(user_repos_df)
        all_repos_df = self._preprocess_repositories(all_repos_df)
        
        # Create feature matrices
        user_feature_matrix = self._create_feature_matrix(user_repos_df)
        all_repos_feature_matrix = self._create_feature_matrix(all_repos_df)
        
        # Calculate similarity
        if similarity_method == 'cosine':
            similarity_matrix = cosine_similarity(all_repos_feature_matrix, user_feature_matrix)
        elif similarity_method == 'euclidean':
            # Convert distance to similarity
            distances = euclidean_distances(all_repos_feature_matrix, user_feature_matrix)
            similarity_matrix = 1 / (1 + distances)
        else:
            raise ValueError("Unsupported similarity method")
        
        # Calculate average similarity
        avg_similarities = similarity_matrix.mean(axis=1)
        
        # Get top recommendations
        top_indices = avg_similarities.argsort()[-top_n:][::-1]
        recommended_repos = all_repos_df.iloc[top_indices]
        
        return recommended_repos
    
    def generate_cluster_recommendations(
        self, 
        github_client, 
        top_clusters: int = 3, 
        repos_per_cluster: int = 5
    ) -> pd.DataFrame:
        """
        Generate recommendations based on repository clusters
        
        :param github_client: Authenticated PyGithub client
        :param top_clusters: Number of top clusters to recommend from
        :param repos_per_cluster: Number of repositories to recommend per cluster
        :return: DataFrame of recommended repositories
        """
        # Get current user
        user = github_client.get_user()
        username = user.login
        
        # Connect to database
        with sqlite3.connect(self.database_path) as conn:
            # Fetch user's repositories
            user_repos_df = pd.read_sql_query(
                "SELECT * FROM user_repositories WHERE username = ?", 
                conn, 
                params=(username,)
            )
        
        # Preprocess repositories
        user_repos_df = self._preprocess_repositories(user_repos_df)
        
        # Analyze user's repository languages and topics
        language_counts = user_repos_df['language'].value_counts()
        top_languages = language_counts.head(top_clusters).index.tolist()
        
        # Connect to database again to fetch recommendations
        with sqlite3.connect(self.database_path) as conn:
            # Fetch repositories in top languages
            cluster_recommendations = []
            for lang in top_languages:
                cluster_query = """
                SELECT * FROM user_repositories 
                WHERE username != ? AND language = ? 
                AND full_name NOT IN (
                    SELECT full_name FROM user_repositories WHERE username = ?
                )
                ORDER BY stars DESC
                LIMIT ?
                """
                cluster_repos = pd.read_sql_query(
                    cluster_query, 
                    conn, 
                    params=(username, lang, username, repos_per_cluster)
                )
                cluster_recommendations.append(cluster_repos)
        
        # Combine and return recommendations
        if cluster_recommendations:
            return pd.concat(cluster_recommendations)
        else:
            return pd.DataFrame()

# Flask routes to integrate recommendations
def create_recommendation_routes(app, recommender):
    """
    Create routes for repository recommendations
    
    :param app: Flask app instance
    :param recommender: RepositoryRecommender instance
    :return: None
    """
    @app.route('/recommendations')
    def recommendations():
        from flask import session, redirect, url_for, render_template, flash
        
        if 'access_token' not in session:
            return redirect(url_for('login'))
        
        try:
            # Create GitHub client
            github_client = Github(session['access_token'])
            
            # Generate recommendations
            standard_recs = recommender.generate_recommendations(
                github_client, 
                top_n=10
            )
            
            # Generate cluster-based recommendations
            cluster_recs = recommender.generate_cluster_recommendations(
                github_client, 
                top_clusters=3, 
                repos_per_cluster=5
            )
            
            return render_template(
                'recommendations.html',
                username=session['username'],
                avatar_url=session.get('avatar_url', ''),
                standard_recommendations=standard_recs.to_dict('records'),
                cluster_recommendations=cluster_recs.to_dict('records')
            )
        
        except Exception as e:
            flash(f"Error generating recommendations: {e}")
            return redirect(url_for('repositories'))

# Main execution
def create_app():
    from flask import Flask, session
    import os
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
    app.config['GITHUB_CLIENT_ID'] = os.getenv('GITHUB_CLIENT_ID')
    app.config['GITHUB_CLIENT_SECRET'] = os.getenv('GITHUB_CLIENT_SECRET')
    
    # Create recommender
    recommender = RepositoryRecommender()
    
    # Add routes
    create_recommendation_routes(app, recommender)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)